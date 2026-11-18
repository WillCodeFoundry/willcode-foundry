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
        description = _describe_checkout(Git(checkout), branch)
        if description is not None:
            lines.append(f"{name} {checkout} on {branch}: {description}")
    return lines


class _OriginComparisonFailure(Exception):
    """Why a checkout can't be compared with origin; its message is the reason."""


def _describe_checkout(git: Git, branch: str) -> str | None:
    """What this checkout has that origin lacks, or why that can't be told, in words; None when origin has it all.
    The one place that says "can't tell"."""
    try:
        uncommitted, not_pushed = _compare_with_origin(git, branch)
    except _OriginComparisonFailure as failure:
        return f"can't tell: {failure}"
    if uncommitted and not_pushed:
        return "uncommitted changes and commits not pushed"
    if uncommitted:
        return "uncommitted changes"
    return "commits not pushed" if not_pushed else None


def _compare_with_origin(git: Git, branch: str) -> tuple[bool, bool]:
    """Whether the checkout has uncommitted changes, and whether origin/``branch``, freshly fetched, lacks commits on
    the branch, or at HEAD, which a detached HEAD moves off it. Raises _OriginComparisonFailure when origin can't be
    reached or a git command fails."""
    try:
        uncommitted = bool(git.output("status", "--porcelain").strip())
        fetch = git.run_captured("fetch", "-q", "origin", branch)
        if fetch.returncode != 0:
            raise _OriginComparisonFailure(f"origin can't be reached: {_first_line(fetch.stderr)}")
        not_pushed = any(
            int(git.output("rev-list", "--count", f"origin/{branch}..{rev}")) > 0
            for rev in (f"refs/heads/{branch}", "HEAD")
        )
    except GitError as error:
        raise _OriginComparisonFailure(f"can't read it: {error}") from error
    return uncommitted, not_pushed


def _first_line(stderr: str) -> str:
    return stderr.strip().splitlines()[0] if stderr.strip() else "no message"
