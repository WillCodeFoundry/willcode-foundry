from collections.abc import Callable
from pathlib import Path

import pytest

from foundry.task import Task
from tests.agent_kit import AGENT_KIT_PATH, TASK


@pytest.fixture
def kit_env(tmp_path: Path, sandbox_variables: Callable[[Task], dict[str, str]]) -> dict[str, str]:
    """The variables a sandbox for TASK gets, so the kit is tested with exactly the names foundry sets.

    Pointed at this repository's agent kit and at checkouts under tmp_path/work; a test
    replaces any other variable it needs, e.g. AGENT_REPO_URL for a local origin.
    """
    return {
        **sandbox_variables(TASK),
        "AGENT_KIT_DIR": str(AGENT_KIT_PATH),
        "AGENT_PROJECT_DIR": str(tmp_path / "work" / "p"),
        "AGENT_NOTES_DIR": str(tmp_path / "work" / "p-notes"),
    }
