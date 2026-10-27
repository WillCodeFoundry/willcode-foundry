import dataclasses
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from agent_runtime import contract, harden
from agent_runtime.agent_kit import AgentKit
from foundry.session import SessionVariables
from foundry.task import Task

SETTINGS = json.loads(AgentKit(Path(__file__).parents[2] / "agent-kit").managed_settings.read_text())
"""The kit's managed settings, as Claude Code reads them."""
HOOK_COMMANDS = {
    event: [hook["command"] for entry in entries for hook in entry["hooks"]]
    for event, entries in SETTINGS["hooks"].items()
}
"""Each hook event's commands, as written in the managed settings."""


def hook_command(command: str, kit_dir: Path) -> str:
    """A managed hook's command with the kit's runtime in place of the link root mode makes to it,
    harden.SANDBOX.hooks_runtime_link: a host has no such link. The rest runs as written."""
    link = str(harden.SANDBOX.hooks_runtime_link)
    assert command.count(link) == 1, command
    return command.replace(link, str(AgentKit(kit_dir).runtime))


@pytest.fixture
def kit_env(
    tmp_path: Path, built_kit: Path, session_variables: Callable[[Task], SessionVariables]
) -> Callable[[Task], dict[str, str]]:
    """The variables a sandbox for a task gets, so the kit is tested with exactly the names foundry sets.

    Pointed at the agent kit as delivered, with its runtime built (``built_kit``), and at checkouts
    under tmp_path/work (the notes checkout beside the code one, at tmp_path/work/p-notes); a test
    replaces any other variable it needs, e.g. AGENT_REPO_URL for a local origin.
    """

    def env(task: Task) -> dict[str, str]:
        variables = dataclasses.replace(
            session_variables(task), agent_kit_dir=built_kit, project_dir=str(tmp_path / "work" / "p")
        )
        return variables.to_env()

    return env


def runtime_command(kit_dir: Path, *args: str) -> list[str]:
    """A call into the runtime built into ``kit_dir``: contract.command's, with only its interpreter replaced by
    this one, so a flag added there reaches these tests too.

    The tests that run a command exactly as written (managed settings, the git hooks' stubs) use the
    template's interpreter, /usr/bin/python3, as the sandbox does.
    """
    python, *rest = contract.command(kit_dir, *args)
    assert python == contract.PYTHON
    return [sys.executable, *rest]
