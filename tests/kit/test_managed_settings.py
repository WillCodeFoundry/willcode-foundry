"""agent-kit/claude/managed-settings.json: Claude Code refuses to start on a managed file that isn't valid JSON."""

import json
import os
from pathlib import Path

KIT = Path(__file__).parents[2] / "agent-kit"
SETTINGS = json.loads((KIT / "claude" / "managed-settings.json").read_text())


def test_runs_unattended_without_attribution() -> None:
    assert SETTINGS["permissions"]["defaultMode"] == "bypassPermissions"
    assert SETTINGS["skipDangerousModePermissionPrompt"] is True
    assert SETTINGS["attribution"] == {"commit": "", "pr": ""}


def test_only_managed_hooks_and_rules_apply() -> None:
    assert SETTINGS["allowManagedHooksOnly"] is True
    assert SETTINGS["allowManagedPermissionRulesOnly"] is True


def test_every_hook_command_is_an_executable_in_the_kit() -> None:
    commands = [hook["command"] for event in SETTINGS["hooks"].values() for entry in event for hook in entry["hooks"]]
    assert commands
    for command in commands:
        path = Path(command.strip('"').replace("$AGENT_KIT_DIR", str(KIT)))
        assert path.is_file() and os.access(path, os.X_OK), command
