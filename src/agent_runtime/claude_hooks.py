"""Claude Code's hooks, as managed settings run them: the tool call or event as JSON on stdin.

``guard_bash`` (PreToolUse, on Bash) refuses a command that would skip or reconfigure the git hooks.
``session_check`` (Stop) refuses to end the session while either checkout has uncommitted or unpushed work,
or can't be checked.
Both are guardrails against mistakes, not boundaries: see "What protects what" in the README.
"""

import json
import re
import shlex
import sys
from pathlib import Path
from typing import TextIO

from agent_runtime import contract
from agent_runtime.git import Git

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
    return 2


def session_check(
    stdin: TextIO | None = None, stdout: TextIO | None = None, env: contract.Environ | None = None
) -> int:
    """Block the stop, with the reason as the agent's next instruction, while work is unsaved.

    The rule: a session cannot end with uncommitted or unpushed changes.
    """
    environ = env or contract.read_environ()
    if _stop_hook_active(stdin or sys.stdin):
        return 0  # already looping on this hook: let the stop through rather than spin
    problems = [
        *_unsaved_work(environ.project_dir, environ.task_branch, "code checkout"),
        *_unsaved_work(environ.notes_dir, environ.notes_branch, "notes checkout"),
    ]
    if not problems:
        return 0
    reason = (
        f"Cannot end the session yet: {'; '.join(problems)}. "
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


def _unsaved_work(checkout: Path, branch: str, label: str) -> list[str]:
    """What in ``checkout`` isn't saved on origin: uncommitted changes, and commits on ``branch``, or at HEAD if
    that is elsewhere, that origin/``branch`` lacks. A git command failing is a problem too, not a pass."""
    git = Git(checkout)
    status = git.result("status", "--porcelain")
    if status.returncode != 0:
        return [_cant_check(label, ("status", "--porcelain"), status.stderr)]
    problems = [f"{label} has uncommitted changes"] if status.stdout.strip() else []
    git.result("fetch", "-q", "origin", branch)  # offline, the last fetched state is all there is
    for rev in (f"refs/heads/{branch}", "HEAD"):
        args = ("rev-list", "--count", f"origin/{branch}..{rev}")
        ahead = git.result(*args)
        if ahead.returncode != 0:
            return [*problems, _cant_check(label, args, ahead.stderr)]
        if int(ahead.stdout) > 0:
            return [*problems, f"{label} has commits not pushed to origin/{branch}"]
    return problems


def _cant_check(label: str, args: tuple[str, ...], stderr: str) -> str:
    message = stderr.strip().splitlines()[0] if stderr.strip() else "no message"
    return f"{label} can't be checked: `git {' '.join(args)}` failed: {message}"
