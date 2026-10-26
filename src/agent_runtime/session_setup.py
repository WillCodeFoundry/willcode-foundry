"""The agent user's part of preparing a sandbox, run by session-init before it hardens: the git identity,
the checkouts, and the agent's instructions.

Idempotent: safe to run again on a re-attached sandbox. Never needs root, so the tests run it outside a
sandbox. The sandbox has no host checkout: the project is cloned here from AGENT_REPO_URL into
AGENT_PROJECT_DIR. Assumes `foundry task create` has already created the task: its branch, and its notes
folder, holding its TASK.md, on the notes branch. Anything missing is an error, not something to create.
"""

import subprocess
import sys
from pathlib import Path

from agent_runtime import contract, git


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
    role_path = environ.kit_dir / "roles" / environ.role
    if not (role_path / "gitconfig").is_file():
        raise SetupError(f"{role_path}/gitconfig is missing")
    _set_identity(environ, role_path)
    _prepare_checkouts(environ)
    task_md_path = environ.notes_dir / environ.task_file
    # Every task has a TASK.md: foundry task create refuses a template without one.
    if not task_md_path.is_file():
        raise SetupError(
            f"{environ.notes_branch} has no {environ.task_file}; push the task's TASK.md there, then run again."
        )
    _write_instructions(environ, role_path, task_md_path)
    _link_skills(role_path)
    print("session-setup: checkouts ready", flush=True)
    for checkout in (environ.project_dir, environ.notes_dir):
        print(git.run("-C", str(checkout), "status", "-sb").stdout.partition("\n")[0], flush=True)


def _set_identity(environ: contract.Environ, role_path: Path) -> None:
    """Global, so both checkouts share it. Name, email, signing key and shared behaviour all come from the
    role's gitconfig and what it includes."""
    _git("config", "--global", "include.path", str(role_path / "gitconfig"))
    # Lets agents verify commits signed by any role, or by you.
    _git("config", "--global", "gpg.ssh.allowedSignersFile", str(environ.kit_dir / "git" / "allowed_signers"))
    if _git_config("commit.gpgsign") == "true" and not _git_config("user.signingkey"):
        raise SetupError(f"{environ.role} signs commits but {role_path}/gitconfig sets no user.signingkey")


def _prepare_checkouts(environ: contract.Environ) -> None:
    project = environ.project_dir
    if not (project / ".git").is_dir():
        project.parent.mkdir(parents=True, exist_ok=True)
        # Blobless partial clone: full history of commits, file contents fetched on demand. Keeps large
        # repositories fast without the limits of --depth.
        _git("clone", "--filter=blob:none", environ.repo_url, str(project))
    _git("config", "core.hooksPath", str(environ.kit_dir / "hooks"), cwd=project)  # read-only mount
    _git("fetch", "origin", cwd=project)

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
        _git("switch", environ.task_branch, cwd=project)
    else:
        _git("switch", "-c", environ.task_branch, "--track", f"origin/{environ.task_branch}", cwd=project)

    notes = environ.notes_dir
    if not notes.is_dir():
        if _has_ref(project, f"refs/heads/{environ.notes_branch}"):
            _git("worktree", "add", str(notes), environ.notes_branch, cwd=project)
        else:
            _git(
                "worktree",
                "add",
                "--track",
                "-b",
                environ.notes_branch,
                str(notes),
                f"origin/{environ.notes_branch}",
                cwd=project,
            )


def _write_instructions(environ: contract.Environ, role_path: Path, task_md_path: Path) -> None:
    """Claude Code loads ~/.claude/CLAUDE.md in every session and follows its @ imports without the approval
    dialog it shows for imports in a project file. Rewritten at every launch, so edits made inside the sandbox
    don't persist."""
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    imports = [environ.kit_dir / "AGENTS.md", role_path / "ROLE.md", task_md_path]
    (claude_dir / "CLAUDE.md").write_text(
        "<!-- Written by session-init at every launch; edits here are discarded. -->\n"
        + "".join(f"@{_escape_spaces(path)}\n" for path in imports)
    )


def _escape_spaces(path: Path) -> str:
    """An @ import needs its spaces escaped."""
    return str(path).replace(" ", "\\ ")


def _link_skills(role_path: Path) -> None:
    """The role's skills: roles/<role>/skills/ holds a link to each skill, and is linked as ~/.claude/skills,
    where Claude Code loads them. Remade at every launch, so a role's changed skills take effect; a role
    without the folder has none."""
    skills_link = Path.home() / ".claude" / "skills"
    if skills_link.exists() and not skills_link.is_symlink():
        raise SetupError(f"{skills_link} is a folder, not the link to the role's skills; remove it, then run again.")
    skills_link.unlink(missing_ok=True)
    if (role_path / "skills").is_dir():
        skills_link.symlink_to(role_path / "skills")


def _git(*args: str, cwd: Path | None = None) -> None:
    """Run git, its output going where this command's goes, unlike git.run: what clone and switch print is
    the setup's progress. A failure stops setup, as git reported it."""
    sys.stdout.flush()
    if subprocess.run(["git", *args], cwd=cwd, check=False).returncode != 0:
        raise SetupError(f"`git {' '.join(args)}` failed; see git's message above")


def _git_config(key: str) -> str:
    return git.run("config", "--get", key).stdout.strip()


def _has_ref(repository: Path, ref: str) -> bool:
    return git.run("-C", str(repository), "show-ref", "-q", "--verify", ref).returncode == 0
