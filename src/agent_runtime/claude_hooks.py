"""Claude Code's hooks, as managed settings run them: the tool call or event as JSON on stdin.

``guard_bash`` (PreToolUse, on Bash) refuses a command that would skip or reconfigure the git hooks.
``session_check`` (Stop) refuses to end the agent run while either checkout has uncommitted or unpushed work,
or can't be checked.
Both are guardrails against mistakes, not boundaries: see docs/security-model.md. Both trust the
environment Claude Code gives them, which a settings file the agent writes can change: session-check reads the
checkouts' paths from the session variables, and runs the git on PATH.
"""

import json
import re
import shlex
import sys
from typing import TextIO

from agent_runtime import contract
from agent_runtime.checkouts import unsaved_work

_BLOCK = 2
"""Claude Code: a PreToolUse hook exiting 2 blocks the tool call and shows its stderr to the agent."""
_NO_VERIFY = re.compile(r"(?<![\w-])--no-verify(?![\w-])")
_QUOTING = re.compile(r"['\"\\]")
_SHELL_PUNCTUATION = "()$`;&|<>{}"
_BYPASS = "git hooks must not be bypassed (--no-verify)"
_RECONFIGURE = "git hook configuration must not be changed"


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
        return _scan(_QUOTING.sub("", command))
    if "--no-verify" in words:
        return _BYPASS
    if any("core.hookspath" in word.lower() for word in words):
        return _RECONFIGURE
    return None


def _scan(text: str) -> str | None:
    if _NO_VERIFY.search(text):
        return _BYPASS
    if "core.hookspath" in text.lower():
        return _RECONFIGURE
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
        "  Fix the cause instead. If you believe this is wrong, record it under\n"
        "  Blockers in PROGRESS.md and ask.",
        file=stderr or sys.stderr,
    )
    return _BLOCK


def session_check(
    stdin: TextIO | None = None, stdout: TextIO | None = None, session: contract.Environ | None = None
) -> int:
    """Block the stop, with the reason as the agent's next instruction, while work is unsaved.

    The rule: a session cannot end with uncommitted or unpushed changes.
    """
    session = session or contract.read_environ()
    if _stop_hook_active(stdin or sys.stdin):
        return 0  # already looping on this hook: let the stop through rather than spin
    problems = unsaved_work(session)
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
