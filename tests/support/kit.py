"""The agent kit as delivered: its managed settings' hook commands, and how the tests call its runtime."""

import json
import sys
from pathlib import Path

from agent_runtime import hardening
from agent_runtime.agent_kit import PYTHON, AgentKit
from tests.support import AGENT_KIT_SOURCE

SETTINGS = json.loads(AgentKit(AGENT_KIT_SOURCE).managed_settings.read_text())
"""The kit's managed settings, as Claude Code reads them."""
HOOK_COMMANDS = {
    event: [hook["command"] for entry in entries for hook in entry["hooks"]]
    for event, entries in SETTINGS["hooks"].items()
}
"""Each hook event's commands, as written in the managed settings."""


def hook_command(command: str, agent_kit_dir: Path) -> str:
    """A managed hook's command with the kit's runtime in place of the link root mode makes to it,
    hardening.SANDBOX.hooks_runtime_link: a host has no such link. The rest runs as written."""
    link = str(hardening.SANDBOX.hooks_runtime_link)
    assert command.count(link) == 1, command
    return command.replace(link, str(AgentKit(agent_kit_dir).runtime))


def runtime_command(agent_kit_dir: Path, *args: str) -> tuple[str, ...]:
    """A call into the runtime built into the kit at ``agent_kit_dir``: contract.command's, with only its
    interpreter replaced by this one, so a flag added there reaches these tests too.

    The tests that run a command exactly as written (managed settings, the git hooks' stubs) use the
    template's interpreter, /usr/bin/python3, as the sandbox does.
    """
    python, *rest = AgentKit(agent_kit_dir).command(*args)
    assert python == PYTHON
    return (sys.executable, *rest)
