"""The agent user's part of preparing a sandbox, run by session-init before it hardens: the git identity,
the checkouts, and the agent's instructions.

Idempotent: safe to run again on a re-attached sandbox. Never needs root, so the tests run it outside a
sandbox. The sandbox has no host checkout: the project is cloned here from AGENT_REPO_URL into
AGENT_CODE_CHECKOUT_DIR. Assumes `foundry task create` has already created the task: its branch, and its task
notes dir, holding its TASK.md, on the notes branch. Anything missing is an error, not something to create.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit, RoleDir
from agent_runtime.atomic_files import atomic_write
from agent_runtime.git import Git


class SetupRefused(Exception):
    """Setup stops: the message, the whole of it, says what was wrong and what to do. It starts with
    "session-setup:", whichever command ran setup."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"session-setup: {reason}")


@dataclass(frozen=True)
class _Checkout:
    """One of the sandbox clone's two working trees, as a refusal names it."""

    name: Literal["code", "notes"]
    dir: Path
    branch: str

    @property
    def git(self) -> Git:
        """git, run in this checkout's working tree."""
        return Git(self.dir)


def set_up(variables: contract.SessionVariables | None = None) -> None:
    """Set the sandbox up: the git identity, both checkouts, and the agent's instructions and skills under ~/.claude.
    Raises SetupRefused when it can't."""
    variables = variables or contract.read_session_variables()
    home = Path.home()
    agent_kit = AgentKit(variables.agent_kit_dir)
    role_dir = agent_kit.role_dir(variables.agent_role)
    # The rule foundry's config applies on the host, applied again here, before anything changes.
    if missing := role_dir.missing_files():
        raise SetupRefused(f"role {variables.agent_role!r}: {role_dir.dir} has no {' or '.join(missing)}")
    _set_identity(variables, agent_kit, role_dir)
    _prepare_checkouts(variables, agent_kit)
    task_md_path = variables.agent_notes_checkout_dir / variables.agent_task_file
    _write_instructions(home, agent_kit, role_dir, task_md_path)
    _link_skills(home, role_dir)
    print("session-setup: checkouts ready", flush=True)
    for checkout_dir in (variables.agent_code_checkout_dir, variables.agent_notes_checkout_dir):
        print(Git(checkout_dir).run_captured("status", "-sb").stdout.partition("\n")[0], flush=True)


def _set_identity(variables: contract.SessionVariables, agent_kit: AgentKit, role_dir: RoleDir) -> None:
    """Global, so both checkouts share it. Name, email, signing key and shared behaviour all come from the
    role's gitconfig and what it includes. A role that signs without a key is refused before anything is written."""
    if _role_config(role_dir, "commit.gpgsign") == "true" and not _role_config(role_dir, "user.signingkey"):
        raise SetupRefused(f"{variables.agent_role} signs commits but {role_dir.gitconfig} sets no user.signingkey")
    _run_or_refuse(Git(), "config", "--global", "include.path", str(role_dir.gitconfig))
    # Lets agents verify commits signed by any role, or by you.
    _run_or_refuse(Git(), "config", "--global", "gpg.ssh.allowedSignersFile", str(agent_kit.allowed_signers))


def _prepare_checkouts(variables: contract.SessionVariables, agent_kit: AgentKit) -> None:
    """Bring both checkouts to origin's tips. Every refusal comes before any checkout moves, so a refusal leaves both
    exactly as they were. The one exception is the switch, when the code checkout started on another branch."""
    code = _Checkout("code", variables.agent_code_checkout_dir, variables.agent_task_branch)
    notes = _Checkout("notes", variables.agent_notes_checkout_dir, variables.agent_notes_branch)
    project_sandbox_clone = _clone_if_missing(variables)
    _run_or_refuse(project_sandbox_clone, "config", "core.hooksPath", str(agent_kit.git_hooks))  # read-only mount
    _run_or_refuse(project_sandbox_clone, "fetch", "origin")
    _require_task_on_origin(project_sandbox_clone, variables)
    _switch_to_task_branch(code)
    _require_checkouts_can_update(project_sandbox_clone, code, notes)
    _fast_forward(code)
    _add_notes_checkout(project_sandbox_clone, notes)
    _fast_forward(notes)


def _clone_if_missing(variables: contract.SessionVariables) -> Git:
    """The sandbox clone, cloned into the code checkout's dir when it isn't there.

    A blobless partial clone: full history of commits, file contents fetched on demand. It keeps large repositories
    fast without the limits of --depth."""
    code_checkout_dir = variables.agent_code_checkout_dir
    if not (code_checkout_dir / ".git").is_dir():
        code_checkout_dir.parent.mkdir(parents=True, exist_ok=True)
        _run_or_refuse(Git(), "clone", "--filter=blob:none", variables.agent_repo_url, str(code_checkout_dir))
    return Git(code_checkout_dir)


def _require_task_on_origin(project_sandbox_clone: Git, variables: contract.SessionVariables) -> None:
    """The task must already exist on origin, created with its branch and a TASK.md on the notes branch before
    any agent runs. Say so plainly rather than let git fail, and before any checkout moves."""
    missing = [
        f"branch {branch}"
        for branch in (variables.agent_task_branch, variables.agent_notes_branch)
        if not project_sandbox_clone.succeeds("show-ref", "-q", "--verify", f"refs/remotes/origin/{branch}")
    ]
    if missing:
        raise SetupRefused(
            f"task {variables.agent_task_id} has not been created on {variables.agent_repo_url}: missing "
            f"{' '.join(missing)}.\n"
            f"  Create it with: foundry task create <project> {variables.agent_task_id}, "
            "write its TASK.md, then run again."
        )
    # Every task has a TASK.md: foundry task create refuses a template without one.
    task_md_on_origin = f"refs/remotes/origin/{variables.agent_notes_branch}:{variables.agent_task_file}"
    if not project_sandbox_clone.succeeds("cat-file", "-e", task_md_on_origin):
        raise SetupRefused(
            f"{variables.agent_notes_branch} has no {variables.agent_task_file}; push the task's TASK.md there, "
            "then run again."
        )


def _switch_to_task_branch(code: _Checkout) -> None:
    if _has_branch(code.git, code.branch):
        _run_or_refuse(code.git, "switch", code.branch)
    else:
        _run_or_refuse(code.git, "switch", "-c", code.branch, "--track", f"origin/{code.branch}")


def _add_notes_checkout(project_sandbox_clone: Git, notes: _Checkout) -> None:
    if notes.dir.is_dir():
        return
    if _has_branch(project_sandbox_clone, notes.branch):
        _run_or_refuse(project_sandbox_clone, "worktree", "add", str(notes.dir), notes.branch)
    else:
        _run_or_refuse(
            project_sandbox_clone,
            "worktree",
            "add",
            "--track",
            "-b",
            notes.branch,
            str(notes.dir),
            f"origin/{notes.branch}",
        )


def _require_checkouts_can_update(project_sandbox_clone: Git, code: _Checkout, notes: _Checkout) -> None:
    """Refuse, changing nothing, unless both checkouts can be brought to origin's tips."""
    _require_notes_on_branch(notes)
    _require_fast_forward(project_sandbox_clone, code)
    _require_fast_forward(project_sandbox_clone, notes)


def _require_notes_on_branch(notes: _Checkout) -> None:
    """An existing notes checkout must be on the notes branch, or the agent would read another branch's files."""
    if not notes.dir.is_dir():
        return
    current_branch = notes.git.current_branch()
    if current_branch != notes.branch:
        where = f"on branch {current_branch}" if current_branch else "detached"
        raise _checkout_refusal(
            notes,
            f"it is {where}, expected {notes.branch}.",
            "any unpushed commits or uncommitted changes in it",
        )


def _require_fast_forward(project_sandbox_clone: Git, checkout: _Checkout) -> None:
    """Refuse when the checkout's branch can't be fast-forwarded to origin's: it has diverged, or the update would
    overwrite uncommitted changes. A branch only ahead of origin is fine, and so is one not made yet."""
    local_ref, origin_ref = f"refs/heads/{checkout.branch}", f"refs/remotes/origin/{checkout.branch}"
    if not _has_branch(project_sandbox_clone, checkout.branch) or _is_ancestor(
        project_sandbox_clone, origin_ref, local_ref
    ):
        return
    if not _is_ancestor(project_sandbox_clone, local_ref, origin_ref):
        subjects = project_sandbox_clone.run_captured(
            "log", "--format=%s", f"{origin_ref}..{local_ref}"
        ).stdout.splitlines()
        listed = "".join(f"\n    {subject}" for subject in subjects)
        raise _checkout_refusal(
            checkout,
            f"it has diverged from origin/{checkout.branch}. Local commits origin lacks:{listed}",
            f"those {len(subjects)} local commits",
        )
    if checkout.dir.is_dir():
        # A dry run of the update itself, so git gives the reason and nothing is touched.
        dry_run = checkout.git.run_captured("read-tree", "-m", "-u", "-n", local_ref, origin_ref)
        if dry_run.returncode != 0:
            raise _checkout_refusal(
                checkout,
                f"updating it to origin/{checkout.branch} would overwrite uncommitted changes: "
                f"{dry_run.stderr.strip()}",
                "those uncommitted changes",
            )


def _checkout_refusal(checkout: _Checkout, diagnosis: str, discards: str) -> SetupRefused:
    return SetupRefused(
        f"the {checkout.name} checkout {checkout.dir} (branch {checkout.branch}) can't be brought to origin's tip: "
        f"{diagnosis}\n"
        '  To start over, see the README\'s "Recreating a sandbox". Recreating discards '
        f"{discards}."
    )


def _fast_forward(checkout: _Checkout) -> None:
    """Bring the checkout's branch to origin's tip; a branch already there, or ahead, stays."""
    if not _is_ancestor(checkout.git, f"origin/{checkout.branch}", "HEAD"):
        _run_or_refuse(checkout.git, "merge", "--ff-only", f"origin/{checkout.branch}")


def _has_branch(git: Git, branch: str) -> bool:
    """Whether the sandbox clone has a local ``branch``, as opposed to only origin's."""
    return git.succeeds("show-ref", "-q", "--verify", f"refs/heads/{branch}")


def _is_ancestor(git: Git, older: str, newer: str) -> bool:
    """Whether ``newer`` already holds ``older``: equal to it, or ahead of it."""
    return git.succeeds("merge-base", "--is-ancestor", older, newer)


def _write_instructions(home: Path, agent_kit: AgentKit, role_dir: RoleDir, task_md_path: Path) -> None:
    """Claude Code loads ~/.claude/CLAUDE.md at the start of every agent run, and follows its @ imports without
    the approval dialog it shows for imports in a project file. Rewritten at every launch, so edits made inside
    the sandbox don't persist."""
    claude_md = home / ".claude" / "CLAUDE.md"
    imports = [agent_kit.agents_md, role_dir.role_md, task_md_path]
    text = "<!-- Written by session-init at every launch; edits here are discarded. -->\n" + "".join(
        f"@{_escape_spaces(path)}\n" for path in imports
    )
    try:
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(claude_md, text.encode())  # a link left in its place is replaced, not written through
    except OSError as error:
        raise SetupRefused(f"can't write the agent's instructions to {claude_md}: {error.strerror}") from None


def _escape_spaces(path: Path) -> str:
    """An @ import needs its spaces escaped."""
    return str(path).replace(" ", "\\ ")


def _link_skills(home: Path, role_dir: RoleDir) -> None:
    """The role's skills: roles/<role>/skills/ holds a link to each skill, and is linked as ~/.claude/skills,
    where Claude Code loads them. Remade at every launch, so a role's changed skills take effect; a role
    without the dir has none.

    Whatever else is there is removed, so the agent sees only its role's skills: sbx's Claude template ships
    the dir holding the skills synced from the account that built it (skills/synced/<org>_<account>/)."""
    skills_link = home / ".claude" / "skills"
    try:
        if skills_link.is_dir() and not skills_link.is_symlink():
            shutil.rmtree(skills_link)
        else:
            skills_link.unlink(missing_ok=True)
        if role_dir.skills.is_dir():
            skills_link.parent.mkdir(parents=True, exist_ok=True)
            skills_link.symlink_to(role_dir.skills)
    except OSError as error:
        raise SetupRefused(f"can't link the role's skills as {skills_link}: {error.strerror}") from None


def _run_or_refuse(git: Git, *args: str) -> None:
    """Run a step of the setup, git's output going where this command's goes: what clone and switch print is
    the setup's progress. A failure refuses, pointing at git's own message."""
    if not git.run_visibly(*args):
        raise SetupRefused(f"`{git.describe(*args)}` failed; see git's message above")


def _role_config(role_dir: RoleDir, key: str) -> str:
    """``key`` as the role's gitconfig and what it includes set it; empty when they don't."""
    return Git().run_captured("config", "--file", str(role_dir.gitconfig), "--includes", "--get", key).stdout.strip()
