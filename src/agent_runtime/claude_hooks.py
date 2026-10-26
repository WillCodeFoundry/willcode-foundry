"""Claude Code's hooks, as managed settings run them: the tool call or event as JSON on stdin.

``guard_bash`` (PreToolUse, on Bash) refuses a command that would skip or reconfigure the git hooks.
``session_check`` (Stop) refuses to end the session while either checkout has uncommitted or unpushed work.
Both are guardrails against mistakes, not boundaries: see "What protects what" in the README.
"""

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import TextIO

from agent_runtime import contract


def refusal_reason(command: str) -> str | None:
    """Why ``command`` is refused, or None.

    Refuses a word that is --no-verify, or that mentions core.hooksPath. A quoted word stays one word,
    so a commit message that mentions --no-verify passes. Accepted misses, on purpose, to keep this
    simple: ``git commit -n``, abbreviations such as --no-ver, --no-verify inside ``sh -c "..."``, and
    ``git config --get core.hooksPath`` being refused although it only reads.
    """
    try:
        words = shlex.split(command)
    except ValueError:  # unbalanced quotes: refuse rather than guess what runs
        return "the command could not be parsed; quote it so each argument is clear"
    if "--no-verify" in words:
        return "git hooks must not be bypassed (--no-verify)"
    if any("core.hookspath" in word.lower() for word in words):
        return "git hook configuration must not be changed"
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
    problems = []
    if _git(checkout, "status", "--porcelain").stdout.strip():
        problems.append(f"{label} has uncommitted changes")
    _git(checkout, "fetch", "-q", "origin", branch)  # offline, the last fetched state is all there is
    if _git(checkout, "log", "--oneline", f"origin/{branch}..HEAD").stdout.strip():
        problems.append(f"{label} has commits not pushed to origin/{branch}")
    return problems


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False)
