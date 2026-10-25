import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest

from foundry.session import SessionVariables
from foundry.task import Task

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"


@pytest.fixture
def kit_env(tmp_path: Path, session_variables: Callable[[Task], SessionVariables]) -> Callable[[Task], dict[str, str]]:
    """The variables a sandbox for a task gets, so the kit is tested with exactly the names foundry sets.

    Pointed at this repository's agent kit and at checkouts under tmp_path/work (the notes
    checkout beside the code one, at tmp_path/work/p-notes); a test replaces any other variable
    it needs, e.g. AGENT_REPO_URL for a local origin.
    """

    def env(task: Task) -> dict[str, str]:
        variables = dataclasses.replace(
            session_variables(task), agent_kit_dir=AGENT_KIT_PATH, project_dir=str(tmp_path / "work" / "p")
        )
        return variables.as_env()

    return env
