from collections.abc import Callable
from pathlib import Path

import pytest

from foundry import session
from foundry.task import Task


@pytest.fixture
def kit_env(tmp_path: Path, built_kit: Path) -> Callable[[Task], dict[str, str]]:
    """The variables a sandbox for a task gets, so the kit is tested with exactly the names foundry sets.

    Pointed at the agent kit as delivered, with its runtime built (``built_kit``), and at checkouts
    under tmp_path/work (the notes checkout beside the code one, at tmp_path/work/p-notes); a test
    replaces any other variable it needs, e.g. AGENT_REPO_URL for a local origin.
    """

    def env(task: Task) -> dict[str, str]:
        return session.session_variables(
            role_name="dev",
            task=task,
            repo_url="git@github.com:o/p.git",
            agent_kit_dir=built_kit,
            code_checkout_dir=tmp_path / "work" / "p",
        ).to_env()

    return env
