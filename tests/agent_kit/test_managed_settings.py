"""agent-kit/claude/managed-settings.json: Claude Code refuses to start on a managed file that isn't valid JSON."""

import json
import os
import subprocess
from pathlib import Path

from agent_runtime import contract
from agent_runtime.__main__ import CLAUDE_HOOKS

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
SETTINGS = json.loads((AGENT_KIT_PATH / "claude" / "managed-settings.json").read_text())
COMMANDS = {
    event: [hook["command"] for entry in entries for hook in entry["hooks"]]
    for event, entries in SETTINGS["hooks"].items()
}


def test_runs_unattended_without_attribution() -> None:
    assert SETTINGS["permissions"]["defaultMode"] == "bypassPermissions"
    assert SETTINGS["skipDangerousModePermissionPrompt"] is True
    assert SETTINGS["attribution"] == {"commit": "", "pr": ""}


def test_only_managed_hooks_and_rules_apply() -> None:
    assert SETTINGS["allowManagedHooksOnly"] is True
    assert SETTINGS["allowManagedPermissionRulesOnly"] is True


def test_every_hook_runs_the_kits_runtime_isolated() -> None:
    """The template's own interpreter, with -I, on the zipapp in the read-only kit: nothing the agent can change."""
    runtime = f'{contract.PYTHON} -I "$AGENT_KIT_DIR/{contract.RUNTIME_PYZ}" hook '
    assert COMMANDS == {
        "PreToolUse": [runtime + "guard-bash"],
        "Stop": [runtime + "session-check"],
    }
    assert {command.removeprefix(runtime) for commands in COMMANDS.values() for command in commands} == set(
        CLAUDE_HOOKS
    )


def test_the_guard_runs_as_written(built_kit: Path) -> None:
    """Claude Code runs a hook's command through a shell, with AGENT_KIT_DIR from the sandbox."""
    call = {"tool_name": "Bash", "tool_input": {"command": "git commit --no-verify -m x"}}

    result = subprocess.run(
        COMMANDS["PreToolUse"][0],
        shell=True,
        env={"PATH": os.environ["PATH"], "AGENT_KIT_DIR": str(built_kit)},
        input=json.dumps(call),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2, result.stderr
    assert "guard-bash: refusing" in result.stderr
