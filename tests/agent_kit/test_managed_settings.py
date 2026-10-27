"""agent-kit/claude/managed-settings.json: Claude Code refuses to start on a managed file that isn't valid JSON."""

import json
import os
import subprocess
from pathlib import Path

from agent_runtime import contract, harden
from agent_runtime.__main__ import CLAUDE_HOOKS
from tests.agent_kit.conftest import HOOK_COMMANDS, SETTINGS, hook_command


def test_runs_unattended_without_attribution() -> None:
    assert SETTINGS["permissions"]["defaultMode"] == "bypassPermissions"
    assert SETTINGS["skipDangerousModePermissionPrompt"] is True
    assert SETTINGS["attribution"] == {"commit": "", "pr": ""}


def test_only_managed_hooks_and_rules_apply() -> None:
    assert SETTINGS["allowManagedHooksOnly"] is True
    assert SETTINGS["allowManagedPermissionRulesOnly"] is True


def test_every_hook_runs_the_kits_runtime_isolated() -> None:
    """The template's own interpreter, with contract.PYTHON_FLAGS, on the runtime through the link root mode makes
    to the kit's: a fixed path in a root-owned folder. No variable: a settings file the agent writes can set Claude
    Code's."""
    runtime = f"{contract.PYTHON} {contract.PYTHON_FLAGS} {harden.SANDBOX.hooks_runtime} hook "
    assert HOOK_COMMANDS == {
        "PreToolUse": [runtime + "guard-bash"],
        "Stop": [runtime + "session-check"],
    }
    assert {command.removeprefix(runtime) for commands in HOOK_COMMANDS.values() for command in commands} == set(
        CLAUDE_HOOKS
    )


def test_the_guard_runs_as_written(built_kit: Path) -> None:
    """Claude Code runs a hook's command through a shell; the link's target stands in for the link."""
    call = {"tool_name": "Bash", "tool_input": {"command": "git commit --no-verify -m x"}}

    result = subprocess.run(
        hook_command(HOOK_COMMANDS["PreToolUse"][0], built_kit),
        shell=True,
        env={"PATH": os.environ["PATH"]},
        input=json.dumps(call),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2, result.stderr
    assert "guard-bash: refusing" in result.stderr
