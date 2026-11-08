"""The rules of Claude Code's hooks. agent_runtime.commands.claude_hook reads the hook's JSON and writes its reply.

``refusal_reason`` is guard-bash's rule (PreToolUse, on Bash): a command must not skip or reconfigure the git hooks.
``unsaved_work`` is session-check's (Stop): the agent may not stop while either checkout has uncommitted or unpushed
work, or can't be checked.
Both are guardrails against mistakes, not boundaries: see docs/security-model.md. Both trust the
environment Claude Code gives them, which a settings file the agent writes can change: session-check reads the
checkouts' paths from the session variables, and runs the git on PATH.
"""

import re
import shlex
from pathlib import Path

from agent_runtime import contract
from agent_runtime.git import Git, GitError

_NO_VERIFY = re.compile(r"(?<![\w-])--no-verify(?![\w-])")
_QUOTING = re.compile(r"['\"\\]")
_SHELL_PUNCTUATION = "()$`;&|<>{}"
_BYPASS_REASON = "git hooks must not be bypassed (--no-verify)"
_RECONFIGURE_REASON = "git hook configuration must not be changed"


def refusal_reason(command: str) -> str | None:
    """Why ``command`` is refused, or None.

    Refuses a word that is --no-verify once shell punctuation is stripped, so ``$(git commit --no-verify)``
    counts, or that mentions core.hooksPath. A quoted word stays one word, so a commit message that mentions
    --no-verify passes. Nothing is dropped: a heredoc's body can run. What shlex can't split, a comment's
    apostrophe say, is scanned whole with its quoting removed. Accepted misses, on purpose, to keep this simple:
    ``git commit -n``, abbreviations such as --no-ver, --no-verify inside ``sh -c "..."``, and
    ``git config --get core.hooksPath`` being refused although it only reads.
    """
    try:
        words = [word.strip(_SHELL_PUNCTUATION) for word in shlex.split(command)]
    except ValueError:  # unbalanced quotes, an apostrophe in prose say: scan the whole text, unquoted
        return _refusal_reason_in_text(_QUOTING.sub("", command))
    if "--no-verify" in words:
        return _BYPASS_REASON
    if any("core.hookspath" in word.lower() for word in words):
        return _RECONFIGURE_REASON
    return None


def _refusal_reason_in_text(text: str) -> str | None:
    if _NO_VERIFY.search(text):
        return _BYPASS_REASON
    if "core.hookspath" in text.lower():
        return _RECONFIGURE_REASON
    return None


def unsaved_work(variables: contract.SessionVariables) -> list[str]:
    """What in either checkout isn't saved on origin: uncommitted or unpushed changes, or a checkout that can't be
    checked. Empty when both are saved."""
    return [
        *_unsaved_work(variables.agent_code_checkout_dir, variables.agent_task_branch, "code checkout"),
        *_unsaved_work(variables.agent_notes_checkout_dir, variables.agent_notes_branch, "notes checkout"),
    ]


class _CantCheck(Exception):
    """A git command session-check needs failed; the message names it and git's first line."""


def _unsaved_work(checkout: Path, branch: str, label: str) -> list[str]:
    """What in ``checkout`` isn't saved on origin. When git can't tell, that is reported too: the stop is
    blocked rather than let through unchecked."""
    git = Git(checkout)
    try:
        return [*_uncommitted_problems(git, label), *_unpushed_problems(git, branch, label)]
    except (_CantCheck, GitError) as error:
        return [f"{label} can't be checked: {error}"]


def _uncommitted_problems(git: Git, label: str) -> list[str]:
    return [f"{label} has uncommitted changes"] if _checked_output(git, "status", "--porcelain").strip() else []


def _unpushed_problems(git: Git, branch: str, label: str) -> list[str]:
    """Commits origin/``branch`` lacks: on the branch, and at HEAD, which a detached HEAD moves off it."""
    git.run_captured("fetch", "-q", "origin", branch)  # offline, the last fetched state is all there is
    for rev in (f"refs/heads/{branch}", "HEAD"):
        if int(_checked_output(git, "rev-list", "--count", f"origin/{branch}..{rev}")) > 0:
            return [f"{label} has commits not pushed to origin/{branch}"]
    return []


def _checked_output(git: Git, *args: str) -> str:
    """The command's output; a failure raises _CantCheck naming it, with git's first line."""
    result = git.run_captured(*args)
    if result.returncode != 0:
        first_line = result.stderr.strip().splitlines()[0] if result.stderr.strip() else "no message"
        raise _CantCheck(f"`{git.describe(*args)}` failed: {first_line}")
    return result.stdout
