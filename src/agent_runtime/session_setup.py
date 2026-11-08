"""The agent user's part of preparing a sandbox, run by session-init before it hardens: the git identity,
the checkouts, and the agent's instructions.

Idempotent: safe to run again on a re-attached sandbox. Never needs root, so the tests run it outside a
sandbox. The sandbox has no host checkout: the project is cloned here from AGENT_REPO_URL into
AGENT_CODE_CHECKOUT_DIR. Assumes `foundry task create` has already created the task: its branch, and its task
notes dir, holding its TASK.md, on the notes branch. Anything missing is an error, not something to create.
"""

import shutil
from pathlib import Path

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit, RoleDir
from agent_runtime.atomic_files import atomic_write
from agent_runtime.git import Git


class SetupError(Exception):
    """A precondition setup doesn't create is missing; the message, the whole of it, says what to do."""


def session_setup(variables: contract.SessionVariables | None = None, home: Path | None = None) -> None:
    """Set the sandbox up, the agent's instructions under ``home`` (the user's by default). Raises SetupError
    on a missing precondition."""
    variables = variables or contract.read_session_variables()
    try:
        _set_up(variables, home or Path.home())
    except SetupError as error:
        raise SetupError(f"session-setup: {error}") from None


def _set_up(variables: contract.SessionVariables, home: Path) -> None:
    agent_kit = AgentKit(variables.agent_kit_dir)
    role_dir = agent_kit.role_dir(variables.agent_role)
    # The rule foundry's config applies on the host, applied again here, before anything changes.
    if missing := role_dir.missing_files():
        raise SetupError(f"role {variables.agent_role!r}: {role_dir.dir} has no {' or '.join(missing)}")
    _set_identity(variables, agent_kit, role_dir)
    _prepare_checkouts(variables, agent_kit)
    task_md_path = variables.agent_notes_checkout_dir / variables.agent_task_file
    # Every task has a TASK.md: foundry task create refuses a template without one.
    if not task_md_path.is_file():
        raise SetupError(
            f"{variables.agent_notes_branch} has no {variables.agent_task_file}; push the task's TASK.md there, "
            "then run again."
        )
    _write_instructions(home, agent_kit, role_dir, task_md_path)
    _link_skills(home, role_dir)
    print("session-setup: checkouts ready", flush=True)
    for checkout_dir in (variables.agent_code_checkout_dir, variables.agent_notes_checkout_dir):
        print(Git(checkout_dir).run_captured("status", "-sb").stdout.partition("\n")[0], flush=True)


def _set_identity(variables: contract.SessionVariables, agent_kit: AgentKit, role_dir: RoleDir) -> None:
    """Global, so both checkouts share it. Name, email, signing key and shared behaviour all come from the
    role's gitconfig and what it includes."""
    _step(Git(), "config", "--global", "include.path", str(role_dir.gitconfig))
    # Lets agents verify commits signed by any role, or by you.
    _step(Git(), "config", "--global", "gpg.ssh.allowedSignersFile", str(agent_kit.allowed_signers))
    if _git_config("commit.gpgsign") == "true" and not _git_config("user.signingkey"):
        raise SetupError(f"{variables.agent_role} signs commits but {role_dir.gitconfig} sets no user.signingkey")


def _prepare_checkouts(variables: contract.SessionVariables, agent_kit: AgentKit) -> None:
    project_sandbox_clone = _clone_if_missing(variables)
    _step(project_sandbox_clone, "config", "core.hooksPath", str(agent_kit.git_hooks))  # read-only mount
    _step(project_sandbox_clone, "fetch", "origin")
    _require_task_on_origin(project_sandbox_clone, variables)
    _switch_to_task_branch(Git(variables.agent_code_checkout_dir), variables)
    _require_notes_on_branch(variables)
    # Every refusal comes before any checkout moves, so a refusal leaves both exactly as they were. The one
    # exception is the switch above, when the code checkout started on another branch.
    _require_fast_forward(project_sandbox_clone, variables.agent_code_checkout_dir, variables.agent_task_branch, "code")
    _require_fast_forward(
        project_sandbox_clone, variables.agent_notes_checkout_dir, variables.agent_notes_branch, "notes"
    )
    _fast_forward(Git(variables.agent_code_checkout_dir), variables.agent_task_branch)
    _add_notes_checkout(project_sandbox_clone, variables)
    _fast_forward(Git(variables.agent_notes_checkout_dir), variables.agent_notes_branch)


def _clone_if_missing(variables: contract.SessionVariables) -> Git:
    """The sandbox clone, cloned into the code checkout's dir when it isn't there.

    A blobless partial clone: full history of commits, file contents fetched on demand. It keeps large repositories
    fast without the limits of --depth."""
    code_checkout_dir = variables.agent_code_checkout_dir
    if not (code_checkout_dir / ".git").is_dir():
        code_checkout_dir.parent.mkdir(parents=True, exist_ok=True)
        _step(Git(), "clone", "--filter=blob:none", variables.agent_repo_url, str(code_checkout_dir))
    return Git(code_checkout_dir)


def _require_task_on_origin(project_sandbox_clone: Git, variables: contract.SessionVariables) -> None:
    """The task must already exist on origin, created with its branch and a TASK.md on the notes branch before
    any agent runs. Say so plainly rather than let git fail."""
    missing = [
        f"branch {branch}"
        for branch in (variables.agent_task_branch, variables.agent_notes_branch)
        if not project_sandbox_clone.succeeds("show-ref", "-q", "--verify", f"refs/remotes/origin/{branch}")
    ]
    if missing:
        raise SetupError(
            f"task {variables.agent_task_id} has not been created on {variables.agent_repo_url}: missing "
            f"{' '.join(missing)}.\n"
            f"  Create it with: foundry task create <project> {variables.agent_task_id}, "
            "write its TASK.md, then run again."
        )


def _switch_to_task_branch(code_checkout: Git, variables: contract.SessionVariables) -> None:
    branch = variables.agent_task_branch
    if code_checkout.succeeds("show-ref", "-q", "--verify", f"refs/heads/{branch}"):
        _step(code_checkout, "switch", branch)
    else:
        _step(code_checkout, "switch", "-c", branch, "--track", f"origin/{branch}")


def _add_notes_checkout(project_sandbox_clone: Git, variables: contract.SessionVariables) -> None:
    notes_checkout_dir, branch = variables.agent_notes_checkout_dir, variables.agent_notes_branch
    if notes_checkout_dir.is_dir():
        return
    if project_sandbox_clone.succeeds("show-ref", "-q", "--verify", f"refs/heads/{branch}"):
        _step(project_sandbox_clone, "worktree", "add", str(notes_checkout_dir), branch)
    else:
        _step(
            project_sandbox_clone,
            "worktree",
            "add",
            "--track",
            "-b",
            branch,
            str(notes_checkout_dir),
            f"origin/{branch}",
        )


def _require_notes_on_branch(variables: contract.SessionVariables) -> None:
    """An existing notes checkout must be on the notes branch, or the agent would read another branch's files."""
    if not variables.agent_notes_checkout_dir.is_dir():
        return
    found = Git(variables.agent_notes_checkout_dir).current_branch()
    if found != variables.agent_notes_branch:
        where = f"on branch {found}" if found else "detached"
        raise _refusal(
            "notes",
            variables.agent_notes_checkout_dir,
            variables.agent_notes_branch,
            f"it is {where}, expected {variables.agent_notes_branch}.",
            "any unpushed commits or uncommitted changes in it",
        )


def _require_fast_forward(project_sandbox_clone: Git, checkout_dir: Path, branch: str, label: str) -> None:
    """Refuse, changing nothing, when the branch can't be fast-forwarded to origin's: it has diverged, or the
    update would overwrite uncommitted changes. A branch only ahead of origin is fine."""
    local, remote = f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"
    if not project_sandbox_clone.succeeds("show-ref", "-q", "--verify", local) or project_sandbox_clone.succeeds(
        "merge-base", "--is-ancestor", remote, local
    ):
        return
    if not project_sandbox_clone.succeeds("merge-base", "--is-ancestor", local, remote):
        subjects = project_sandbox_clone.run_captured("log", "--format=%s", f"{remote}..{local}").stdout.splitlines()
        listed = "".join(f"\n    {subject}" for subject in subjects)
        raise _refusal(
            label,
            checkout_dir,
            branch,
            f"it has diverged from origin/{branch}. Local commits origin lacks:{listed}",
            f"those {len(subjects)} local commits",
        )
    if checkout_dir.is_dir():
        # A dry run of the update itself, so git gives the reason and nothing is touched.
        dry_run = Git(checkout_dir).run_captured("read-tree", "-m", "-u", "-n", local, remote)
        if dry_run.returncode != 0:
            raise _refusal(
                label,
                checkout_dir,
                branch,
                f"updating it to origin/{branch} would overwrite uncommitted changes: {dry_run.stderr.strip()}",
                "those uncommitted changes",
            )


def _refusal(label: str, checkout_dir: Path, branch: str, diagnosis: str, discards: str) -> SetupError:
    return SetupError(
        f"the {label} checkout {checkout_dir} (branch {branch}) can't be brought to origin's tip: {diagnosis}\n"
        '  To start over, see the README\'s "Recreating a sandbox". Recreating discards '
        f"{discards}."
    )


def _fast_forward(git: Git, branch: str) -> None:
    """Bring the branch checked out where ``git`` runs to origin's tip; a branch already there, or ahead, stays."""
    if not git.succeeds("merge-base", "--is-ancestor", f"origin/{branch}", "HEAD"):
        _step(git, "merge", "--ff-only", f"origin/{branch}")


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
        raise SetupError(f"can't write the agent's instructions to {claude_md}: {error.strerror}") from None


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
        raise SetupError(f"can't link the role's skills as {skills_link}: {error.strerror}") from None


def _step(git: Git, *args: str) -> None:
    """Run a step of the setup, git's output going where this command's goes: what clone and switch print is
    the setup's progress. A failure stops setup, as git reported it."""
    if not git.run_visibly(*args):
        raise SetupError(f"`{git.describe(*args)}` failed; see git's message above")


def _git_config(key: str) -> str:
    return Git().run_captured("config", "--get", key).stdout.strip()
