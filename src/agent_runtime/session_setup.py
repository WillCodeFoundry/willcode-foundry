"""The agent user's part of preparing a sandbox, run by session-init before it hardens: the git identity,
the checkouts, and the agent's instructions.

Idempotent: safe to run again on a re-attached sandbox. Never needs root, so the tests run it outside a
sandbox. The sandbox has no host checkout: the project is cloned here from AGENT_REPO_URL into
AGENT_CODE_CHECKOUT_DIR. Assumes `foundry task create` has already created the task: its branch, and its task
notes dir, holding its TASK.md, on the notes branch. Anything missing is an error, not something to create.

Progress is logged, and git writes its own output straight to the terminal. The command that runs setup shows both.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit, RoleDir
from agent_runtime.atomic_files import atomic_write
from agent_runtime.git import Git

_LOGGER = logging.getLogger(__name__)


class SetupRefused(Exception):
    """Setup stops: the message, the whole of it, says what was wrong and what to do. It starts with
    "session-setup:", whichever command ran setup."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"session-setup: {reason}")


@dataclass(frozen=True)
class _Checkout:
    """One of the project sandbox clone's two working trees, made by _ProjectSandboxClone.checkout. Its methods
    move or read this working tree; what both checkouts share is the clone's."""

    clone: "_ProjectSandboxClone"
    name: Literal["code", "notes"]
    """As a refusal names the checkout."""
    dir: Path
    branch: str

    def current_branch(self) -> str | None:
        """The branch checked out; None when HEAD is detached."""
        return self._git.current_branch()

    def switch_to_branch(self) -> None:
        """Check out the branch, making it to track origin's when the clone has no local one yet."""
        if self.clone.has_branch(self.branch):
            _run_or_refuse(self._git, "switch", self.branch)
        else:
            _run_or_refuse(self._git, "switch", "-c", self.branch, "--track", f"origin/{self.branch}")

    def update_would_overwrite(self) -> str | None:
        """Why bringing the branch to origin's would overwrite uncommitted changes, in git's words; None when it
        wouldn't. A dry run of the update itself, so nothing is touched."""
        dry_run = self._git.run_captured(
            "read-tree", "-m", "-u", "-n", _local_ref(self.branch), _origin_ref(self.branch)
        )
        return dry_run.stderr.strip() if dry_run.returncode != 0 else None

    def fast_forward(self) -> None:
        """Bring the branch to origin's tip; a branch already there, or ahead, stays. The branch must be the one
        checked out, as the refusals before this make sure."""
        if not self.clone.is_ancestor(_origin_ref(self.branch), _local_ref(self.branch)):
            _run_or_refuse(self._git, "merge", "--ff-only", f"origin/{self.branch}")

    def status_line(self) -> str:
        """The first line of ``git status -sb``: the branch, and how it stands against origin's."""
        return self._git.run_captured("status", "-sb").stdout.partition("\n")[0]

    @property
    def _git(self) -> Git:
        return Git(self.dir)


@dataclass(frozen=True)
class _ProjectSandboxClone:
    """The project's sandbox clone: the refs, config and remote both checkouts share. It moves no working tree; its
    _Checkouts do that. The git details stay in the two classes' methods."""

    dir: Path
    """Where the clone's .git is: the code checkout's dir."""

    @classmethod
    def clone_if_missing(cls, url: str, code_checkout_dir: Path) -> "_ProjectSandboxClone":
        """The clone in ``code_checkout_dir``, cloned from ``url`` first when it isn't there.

        A blobless partial clone: full history of commits, file contents fetched on demand. It keeps large
        repositories fast without the limits of --depth."""
        if not (code_checkout_dir / ".git").is_dir():
            code_checkout_dir.parent.mkdir(parents=True, exist_ok=True)
            _run_or_refuse(Git(), "clone", "--filter=blob:none", url, str(code_checkout_dir))
        return cls(code_checkout_dir)

    def use_hooks_in(self, hooks_dir: Path) -> None:
        """Point core.hooksPath at ``hooks_dir``, for both checkouts."""
        _run_or_refuse(self._git, "config", "core.hooksPath", str(hooks_dir))

    def fetch(self) -> None:
        _run_or_refuse(self._git, "fetch", "origin")

    def has_branch(self, branch: str) -> bool:
        """Whether the clone has a local ``branch``, as opposed to only origin's."""
        return self._git.succeeds("show-ref", "-q", "--verify", _local_ref(branch))

    def has_origin_branch(self, branch: str) -> bool:
        """Whether origin had ``branch`` at the last fetch."""
        return self._git.succeeds("show-ref", "-q", "--verify", _origin_ref(branch))

    def has_file_on_origin(self, branch: str, path: str) -> bool:
        """Whether origin's ``branch`` holds a file at ``path``, relative to the checkout's root."""
        return self._git.succeeds("cat-file", "-e", f"{_origin_ref(branch)}:{path}")

    def is_ancestor(self, older_ref: str, newer_ref: str) -> bool:
        """Whether ``newer_ref`` already holds ``older_ref``: equal to it, or ahead of it."""
        return self._git.succeeds("merge-base", "--is-ancestor", older_ref, newer_ref)

    def commits_origin_lacks(self, branch: str) -> list[str]:
        """The subject of each commit on the local ``branch`` that origin's lacks, newest first."""
        log = self._git.run_captured("log", "--format=%s", f"{_origin_ref(branch)}..{_local_ref(branch)}")
        return log.stdout.splitlines()

    def checkout(self, name: Literal["code", "notes"], checkout_dir: Path, branch: str) -> _Checkout:
        """The working tree at ``checkout_dir`` on ``branch``, whether or not it exists yet."""
        return _Checkout(self, name, checkout_dir, branch)

    def add_checkout(self, checkout: _Checkout) -> None:
        """Add ``checkout`` as a working tree on its branch, tracking origin's when there is no local one yet."""
        if self.has_branch(checkout.branch):
            _run_or_refuse(self._git, "worktree", "add", str(checkout.dir), checkout.branch)
        else:
            _run_or_refuse(
                self._git,
                "worktree",
                "add",
                "--track",
                "-b",
                checkout.branch,
                str(checkout.dir),
                f"origin/{checkout.branch}",
            )

    @property
    def _git(self) -> Git:
        return Git(self.dir)


def set_up(variables: contract.SessionVariables) -> None:
    """Set the sandbox up: the git identity, both checkouts, and the agent's instructions and skills under ~/.claude.
    Raises SetupRefused when it can't."""
    home = Path.home()
    agent_kit = AgentKit(variables.agent_kit_dir)
    role_dir = agent_kit.role_dir(variables.agent_role)
    # The rule foundry's config applies on the host, applied again here, before anything changes.
    if missing := role_dir.missing_files():
        raise SetupRefused(f"role {variables.agent_role!r}: {role_dir.dir} has no {' or '.join(missing)}")
    _set_identity(variables, agent_kit, role_dir)
    code, notes = _prepare_checkouts(variables, agent_kit)
    _write_instructions(home, agent_kit, role_dir, notes.dir / variables.agent_task_file)
    _link_skills(home, role_dir)
    _LOGGER.info("session-setup: checkouts ready")
    for checkout in (code, notes):
        _LOGGER.info(checkout.status_line())


def _set_identity(variables: contract.SessionVariables, agent_kit: AgentKit, role_dir: RoleDir) -> None:
    """Global, so both checkouts share it. Name, email, signing key and shared behaviour all come from the
    role's gitconfig and what it includes. A role that signs without a key is refused before anything is written."""
    if _role_config(role_dir, "commit.gpgsign") == "true" and not _role_config(role_dir, "user.signingkey"):
        raise SetupRefused(f"{variables.agent_role} signs commits but {role_dir.gitconfig} sets no user.signingkey")
    _run_or_refuse(Git(), "config", "--global", "include.path", str(role_dir.gitconfig))
    # Lets agents verify commits signed by any role, or by you.
    _run_or_refuse(Git(), "config", "--global", "gpg.ssh.allowedSignersFile", str(agent_kit.allowed_signers))


def _prepare_checkouts(variables: contract.SessionVariables, agent_kit: AgentKit) -> tuple[_Checkout, _Checkout]:
    """Bring both checkouts to origin's tips, and return them: (code, notes). Every refusal comes before any checkout
    moves, so a refusal leaves both exactly as they were. The one exception is the switch, when the code checkout
    started on another branch."""
    project_sandbox_clone = _ProjectSandboxClone.clone_if_missing(
        variables.agent_repo_url, variables.agent_code_checkout_dir
    )
    code = project_sandbox_clone.checkout("code", variables.agent_code_checkout_dir, variables.agent_task_branch)
    notes = project_sandbox_clone.checkout("notes", variables.agent_notes_checkout_dir, variables.agent_notes_branch)
    project_sandbox_clone.use_hooks_in(agent_kit.git_hooks)  # read-only mount
    project_sandbox_clone.fetch()
    _require_task_on_origin(project_sandbox_clone, variables)
    code.switch_to_branch()
    _require_checkouts_can_update(code, notes)
    code.fast_forward()
    if not notes.dir.is_dir():
        project_sandbox_clone.add_checkout(notes)
    notes.fast_forward()
    return code, notes


def _require_task_on_origin(project_sandbox_clone: _ProjectSandboxClone, variables: contract.SessionVariables) -> None:
    """The task must already exist on origin, created with its branch and a TASK.md on the notes branch before
    any agent runs. Say so plainly rather than let git fail, and before any checkout moves."""
    missing = [
        f"branch {branch}"
        for branch in (variables.agent_task_branch, variables.agent_notes_branch)
        if not project_sandbox_clone.has_origin_branch(branch)
    ]
    if missing:
        raise SetupRefused(
            f"task {variables.agent_task_id} has not been created on {variables.agent_repo_url}: missing "
            f"{' '.join(missing)}.\n"
            f"  Create it with: foundry task create <project> {variables.agent_task_id}, "
            "write its TASK.md, then run again."
        )
    # Every task has a TASK.md: foundry task create refuses a template without one.
    if not project_sandbox_clone.has_file_on_origin(variables.agent_notes_branch, variables.agent_task_file):
        raise SetupRefused(
            f"{variables.agent_notes_branch} has no {variables.agent_task_file}; push the task's TASK.md there, "
            "then run again."
        )


def _require_checkouts_can_update(code: _Checkout, notes: _Checkout) -> None:
    """Refuse, changing nothing, unless both checkouts can be brought to origin's tips."""
    _require_notes_on_branch(notes)
    _require_fast_forward(code)
    _require_fast_forward(notes)


def _require_notes_on_branch(notes: _Checkout) -> None:
    """An existing notes checkout must be on the notes branch, or the agent would read another branch's files."""
    if not notes.dir.is_dir():
        return
    current_branch = notes.current_branch()
    if current_branch != notes.branch:
        where = f"on branch {current_branch}" if current_branch else "detached"
        raise _checkout_refusal(
            notes,
            f"it is {where}, expected {notes.branch}.",
            "any unpushed commits or uncommitted changes in it",
        )


def _require_fast_forward(checkout: _Checkout) -> None:
    """Refuse when the checkout's branch can't be fast-forwarded to origin's: it has diverged, or the update would
    overwrite uncommitted changes. A branch only ahead of origin is fine, and so is one not made yet."""
    clone, local_ref, origin_ref = checkout.clone, _local_ref(checkout.branch), _origin_ref(checkout.branch)
    if not clone.has_branch(checkout.branch) or clone.is_ancestor(origin_ref, local_ref):
        return
    if not clone.is_ancestor(local_ref, origin_ref):
        subjects = clone.commits_origin_lacks(checkout.branch)
        listed = "".join(f"\n    {subject}" for subject in subjects)
        raise _checkout_refusal(
            checkout,
            f"it has diverged from origin/{checkout.branch}. Local commits origin lacks:{listed}",
            f"those {len(subjects)} local commits",
        )
    if checkout.dir.is_dir() and (reason := checkout.update_would_overwrite()):
        raise _checkout_refusal(
            checkout,
            f"updating it to origin/{checkout.branch} would overwrite uncommitted changes: {reason}",
            "those uncommitted changes",
        )


def _checkout_refusal(checkout: _Checkout, diagnosis: str, discards: str) -> SetupRefused:
    return SetupRefused(
        f"the {checkout.name} checkout {checkout.dir} (branch {checkout.branch}) can't be brought to origin's tip: "
        f"{diagnosis}\n"
        '  To start over, see the README\'s "Recreating a sandbox". Recreating discards '
        f"{discards}."
    )


def _local_ref(branch: str) -> str:
    return f"refs/heads/{branch}"


def _origin_ref(branch: str) -> str:
    """``branch`` as origin had it at the last fetch."""
    return f"refs/remotes/origin/{branch}"


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
