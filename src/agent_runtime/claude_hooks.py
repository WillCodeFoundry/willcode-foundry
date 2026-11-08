"""Claude Code's hooks, as managed settings run them: the tool call or event as JSON on stdin.

``guard_bash`` (PreToolUse, on Bash) refuses a command that would skip or reconfigure the git hooks.
``session_check`` (Stop) refuses to let the agent stop while either checkout has uncommitted or unpushed work,
or can't be checked.
Both are guardrails against mistakes, not boundaries: see docs/security-model.md. Both trust the
environment Claude Code gives them, which a settings file the agent writes can change: session-check reads the
checkouts' paths from the session variables, and runs the git on PATH.
"""

import json
import re
import shlex
import sys
from pathlib import Path
from typing import TextIO

from agent_runtime import contract
from agent_runtime.git import Git, GitError

_BLOCK_EXIT_CODE = 2
"""Claude Code: a PreToolUse hook exiting 2 blocks the tool call and shows its stderr to the agent."""
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


def guard_bash(stdin: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Read the tool call; exit 2 with the reason on stderr to refuse it, which Claude Code tells the agent."""
    try:
        call = json.load(stdin or sys.stdin)
        command = call.get("tool_input", {}).get("command", "")
    except (json.JSONDecodeError, AttributeError):
        return 0  # not a tool call we understand; don't block
    reason = refusal_reason(command) if isinstance(command, str) else None
    if reason is None:
        return 0
    print(
        f"guard-bash: refusing\n\n  {reason}.\n  Command: {command}\n\n"
        "  Fix the cause instead. If you believe this is wrong, ask in LOG.md,\n"
        '  as "When to stop and ask" in AGENTS.md says.',
        file=stderr or sys.stderr,
    )
    return _BLOCK_EXIT_CODE


def session_check(
    stdin: TextIO | None = None, stdout: TextIO | None = None, variables: contract.SessionVariables | None = None
) -> int:
    """Block the stop, with the reason as the agent's next instruction, while work is unsaved.

    The rule: an agent run cannot end with uncommitted or unpushed changes.
    """
    variables = variables or contract.read_session_variables()
    if _stop_hook_active(stdin or sys.stdin):
        return 0  # already looping on this hook: let the stop through rather than spin
    problems = [
        *_unsaved_work(variables.agent_code_checkout_dir, variables.agent_task_branch, "code checkout"),
        *_unsaved_work(variables.agent_notes_checkout_dir, variables.agent_notes_branch, "notes checkout"),
    ]
    if not problems:
        return 0
    reason = (
        f"Cannot stop yet: {'; '.join(problems)}. "
        'Commit and push that work (see "Git rules" in AGENTS.md), then finish.'
    )
    print(json.dumps({"decision": "block", "reason": reason}), file=stdout or sys.stdout)
    return 0


def _stop_hook_active(stdin: TextIO) -> bool:
    """Whether Claude Code says this stop comes from this hook's own block. Input that isn't the JSON
    it sends is not a reason to let the stop through."""
    try:
        event = json.load(stdin)
    except json.JSONDecodeError:
        return False
    return isinstance(event, dict) and event.get("stop_hook_active") is True


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
