"""`claude-hook`: Claude Code's hooks, as managed settings run them, the tool call or event as JSON on stdin.

The rules are agent_runtime.claude_hooks'. This module speaks Claude Code's hook protocol: what it reads, and how a
reply blocks.
"""

import json
import sys
from typing import TextIO

from agent_runtime import claude_hooks, contract

_BLOCK_EXIT_CODE = 2
"""Claude Code: a PreToolUse hook exiting 2 blocks the tool call and shows its stderr to the agent."""


def guard_bash(stdin: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Read the tool call; exit 2 with the reason on stderr to refuse it, which Claude Code tells the agent."""
    try:
        call = json.load(stdin or sys.stdin)
        command = call.get("tool_input", {}).get("command", "")
    except (json.JSONDecodeError, AttributeError):
        return 0  # not a tool call we understand; don't block
    reason = claude_hooks.refusal_reason(command) if isinstance(command, str) else None
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
    problems = claude_hooks.unsaved_work(variables)
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
