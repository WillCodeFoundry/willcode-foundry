"""Whether the sandbox's two checkouts are saved: committed, and pushed to origin.

session-check refuses to end the agent run on it, and the task command refuses to write the next task state.
"""

from pathlib import Path

from agent_runtime import contract
from agent_runtime.git import Git, GitError


def unsaved_work(session: contract.Environ) -> list[str]:
    """What in either checkout isn't saved on origin, one line each; empty when both are clean and pushed."""
    return [
        *_unsaved_work(session.agent_project_dir, session.agent_task_branch, "code checkout"),
        *_unsaved_work(session.agent_notes_dir, session.agent_notes_branch, "notes checkout"),
    ]


class _CantCheck(Exception):
    """A git command the check needs failed; the message names it and git's first line."""


def _unsaved_work(checkout: Path, branch: str, label: str) -> list[str]:
    """What in ``checkout`` isn't saved on origin. When git can't tell, that is reported too, so the caller
    refuses rather than let unchecked work through."""
    git = Git(checkout)
    try:
        return [*_uncommitted(git, label), *_unpushed(git, branch, label)]
    except (_CantCheck, GitError) as error:
        return [f"{label} can't be checked: {error}"]


def _uncommitted(git: Git, label: str) -> list[str]:
    return [f"{label} has uncommitted changes"] if _checked(git, "status", "--porcelain").strip() else []


def _unpushed(git: Git, branch: str, label: str) -> list[str]:
    """Commits origin/``branch`` lacks, by subject: on the branch, and at HEAD, which a detached HEAD moves off it.

    Naming them lets the agent see which commit is stuck, such as a task state's commit the human's move overtook.
    """
    git.run_captured("fetch", "-q", "origin", branch)  # offline, the last fetched state is all there is
    for rev in (f"refs/heads/{branch}", "HEAD"):
        if subjects := _checked(git, "log", "--format=%s", f"origin/{branch}..{rev}").splitlines():
            return [f"{label} has commits not pushed to origin/{branch}: {'; '.join(subjects)}"]
    return []


def _checked(git: Git, *args: str) -> str:
    """The command's output; a failure raises _CantCheck naming it, with git's first line."""
    result = git.run_captured(*args)
    if result.returncode != 0:
        first_line = result.stderr.strip().splitlines()[0] if result.stderr.strip() else "no message"
        raise _CantCheck(f"`{git.describe(*args)}` failed: {first_line}")
    return result.stdout
