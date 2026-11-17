"""Unsaved work: what a checkout has that origin lacks, uncommitted changes or commits not pushed to its branch.

The one definition both users share, in the same words: session-check blocks an agent's stop on it, and
check-unsaved-work reports it after an agent run. What can't be checked is "can't tell", never saved, so a hook that
enforces the rule blocks when it can't check it (design rule 6). That includes origin being out of reach: the last
fetched state is no evidence that origin has the work.

It trusts the environment it is given: the checkouts' paths come from the session variables, and it runs the git on
PATH. See docs/security-model.md.
"""

from agent_runtime import contract
from agent_runtime.git import Git, GitError


def describe_unsaved_work(variables: contract.SessionVariables) -> list[str]:
    """One line for each checkout with unsaved work, or that can't be checked, naming it, its dir and its branch.
    Empty when both are saved on origin."""
    checkouts = (
        ("code checkout", variables.agent_code_checkout_dir, variables.agent_task_branch),
        ("notes checkout", variables.agent_notes_checkout_dir, variables.agent_notes_branch),
    )
    lines = []
    for name, checkout, branch in checkouts:
        problem = _unsaved_work(Git(checkout), branch)
        if problem is not None:
            lines.append(f"{name} {checkout} on {branch}: {problem}")
    return lines


class _CantTell(Exception):
    """Why a checkout's unsaved work can't be told."""


def _unsaved_work(git: Git, branch: str) -> str | None:
    """What in this checkout origin lacks, in words; None when origin has it all."""
    try:
        uncommitted = bool(_checked_output(git, "status", "--porcelain").strip())
        not_pushed = _has_commits_not_pushed(git, branch)
    except _CantTell as error:
        return f"can't tell: {error}"
    except GitError as error:
        return f"can't tell: can't read it: {error}"
    if uncommitted and not_pushed:
        return "uncommitted changes and commits not pushed"
    if uncommitted:
        return "uncommitted changes"
    return "commits not pushed" if not_pushed else None


def _has_commits_not_pushed(git: Git, branch: str) -> bool:
    """Whether origin/``branch``, freshly fetched, lacks commits on the branch, or at HEAD, which a detached HEAD
    moves off it."""
    fetch = git.run_captured("fetch", "-q", "origin", branch)
    if fetch.returncode != 0:
        raise _CantTell(f"origin can't be reached: {_first_line(fetch.stderr)}")
    return any(
        int(_checked_output(git, "rev-list", "--count", f"origin/{branch}..{rev}")) > 0
        for rev in (f"refs/heads/{branch}", "HEAD")
    )


def _checked_output(git: Git, *args: str) -> str:
    """The command's output; a failure raises _CantTell naming it, with git's first line."""
    result = git.run_captured(*args)
    if result.returncode != 0:
        raise _CantTell(f"can't read it: `{git.describe(*args)}` failed: {_first_line(result.stderr)}")
    return result.stdout


def _first_line(stderr: str) -> str:
    return stderr.strip().splitlines()[0] if stderr.strip() else "no message"
