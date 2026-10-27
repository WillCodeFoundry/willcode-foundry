"""The agent user's part of preparing a sandbox, run by session-init before it hardens: the git identity,
the checkouts, and the agent's instructions.

Idempotent: safe to run again on a re-attached sandbox. Never needs root, so the tests run it outside a
sandbox. The sandbox has no host checkout: the project is cloned here from AGENT_REPO_URL into
AGENT_PROJECT_DIR. Assumes `foundry task create` has already created the task: its branch, and its notes
folder, holding its TASK.md, on the notes branch. Anything missing is an error, not something to create.
"""

import shlex
import sys
from pathlib import Path

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit, RoleDir
from agent_runtime.files import atomic_write
from agent_runtime.git import Git


class SetupError(Exception):
    """A precondition setup doesn't create is missing; the message says what to do."""


def session_setup(env: contract.Environ | None = None) -> int:
    """Set the sandbox up; on a missing precondition, say what to do and return 1."""
    environ = env or contract.read_environ()
    try:
        _set_up(environ)
    except SetupError as error:
        print(f"session-setup: {error}", file=sys.stderr)
        return 1
    return 0


def _set_up(environ: contract.Environ) -> None:
    kit = AgentKit(environ.kit_dir)
    role = kit.role(environ.role)
    # The rule foundry's config applies on the host, applied again here, before anything changes.
    if missing := role.missing():
        raise SetupError(f"role {environ.role!r}: {role.dir} has no {' or '.join(missing)}")
    _set_identity(environ, kit, role)
    _prepare_checkouts(environ, kit)
    task_md_path = environ.notes_dir / environ.task_file
    # Every task has a TASK.md: foundry task create refuses a template without one.
    if not task_md_path.is_file():
        raise SetupError(
            f"{environ.notes_branch} has no {environ.task_file}; push the task's TASK.md there, then run again."
        )
    _write_instructions(kit, role, task_md_path)
    _link_skills(role)
    print("session-setup: checkouts ready", flush=True)
    for checkout in (environ.project_dir, environ.notes_dir):
        print(Git(checkout).result("status", "-sb").stdout.partition("\n")[0], flush=True)


def _set_identity(environ: contract.Environ, kit: AgentKit, role: RoleDir) -> None:
    """Global, so both checkouts share it. Name, email, signing key and shared behaviour all come from the
    role's gitconfig and what it includes."""
    _step(Git(), "config", "--global", "include.path", str(role.gitconfig))
    # Lets agents verify commits signed by any role, or by you.
    _step(Git(), "config", "--global", "gpg.ssh.allowedSignersFile", str(kit.allowed_signers))
    if _git_config("commit.gpgsign") == "true" and not _git_config("user.signingkey"):
        raise SetupError(f"{environ.role} signs commits but {role.gitconfig} sets no user.signingkey")


def _prepare_checkouts(environ: contract.Environ, kit: AgentKit) -> None:
    project = environ.project_dir
    if not (project / ".git").is_dir():
        project.parent.mkdir(parents=True, exist_ok=True)
        # Blobless partial clone: full history of commits, file contents fetched on demand. Keeps large
        # repositories fast without the limits of --depth.
        _step(Git(), "clone", "--filter=blob:none", environ.repo_url, str(project))
    _step(Git(project), "config", "core.hooksPath", str(kit.hooks))  # read-only mount
    _step(Git(project), "fetch", "origin")

    # The task must already exist on origin, created with its branch and a TASK.md on the notes branch
    # before any agent runs. Say so plainly rather than let git fail.
    missing = [
        f"branch {branch}"
        for branch in (environ.task_branch, environ.notes_branch)
        if not _has_ref(project, f"refs/remotes/origin/{branch}")
    ]
    if missing:
        raise SetupError(
            f"task {environ.task} has not been created on {environ.repo_url}: missing {' '.join(missing)}.\n"
            f"  Create it with: foundry task create <project> {environ.task}, write its TASK.md, then run again."
        )

    if _has_ref(project, f"refs/heads/{environ.task_branch}"):
        _step(Git(project), "switch", environ.task_branch)
    else:
        _step(Git(project), "switch", "-c", environ.task_branch, "--track", f"origin/{environ.task_branch}")

    notes = environ.notes_dir
    if not notes.is_dir():
        if _has_ref(project, f"refs/heads/{environ.notes_branch}"):
            _step(Git(project), "worktree", "add", str(notes), environ.notes_branch)
        else:
            _step(
                Git(project),
                "worktree",
                "add",
                "--track",
                "-b",
                environ.notes_branch,
                str(notes),
                f"origin/{environ.notes_branch}",
            )


def _write_instructions(kit: AgentKit, role: RoleDir, task_md_path: Path) -> None:
    """Claude Code loads ~/.claude/CLAUDE.md in every session and follows its @ imports without the approval
    dialog it shows for imports in a project file. Rewritten at every launch, so edits made inside the sandbox
    don't persist."""
    claude_md = Path.home() / ".claude" / "CLAUDE.md"
    imports = [kit.agents_md, role.role_md, task_md_path]
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


def _link_skills(role: RoleDir) -> None:
    """The role's skills: roles/<role>/skills/ holds a link to each skill, and is linked as ~/.claude/skills,
    where Claude Code loads them. Remade at every launch, so a role's changed skills take effect; a role
    without the folder has none."""
    skills_link = Path.home() / ".claude" / "skills"
    if skills_link.exists() and not skills_link.is_symlink():
        raise SetupError(f"{skills_link} is a folder, not the link to the role's skills; remove it, then run again.")
    skills_link.unlink(missing_ok=True)
    if role.skills.is_dir():
        skills_link.symlink_to(role.skills)


def _step(git: Git, *args: str) -> None:
    """Run a step of the setup, git's output going where this command's goes: what clone and switch print is
    the setup's progress. A failure stops setup, as git reported it."""
    if not git.succeeds(*args, show_output=True):
        folder = ["-C", str(git.folder)] if git.folder is not None else []
        raise SetupError(f"`{shlex.join(['git', *folder, *args])}` failed; see git's message above")


def _git_config(key: str) -> str:
    return Git().result("config", "--get", key).stdout.strip()


def _has_ref(repository: Path, ref: str) -> bool:
    return Git(repository).succeeds("show-ref", "-q", "--verify", ref)
