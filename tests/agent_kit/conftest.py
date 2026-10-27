import dataclasses
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from foundry import paths
from foundry.session import SessionVariables
from foundry.task import Task


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
    """A call into the runtime built into ``kit_dir``, as contract.command makes it, but on this interpreter.

    The tests that run a command exactly as written (managed settings, the git hooks' stubs) use the
    template's interpreter, /usr/bin/python3, as the sandbox does.
    """
    return [sys.executable, "-I", str(paths.runtime_pyz(kit_dir)), *args]
