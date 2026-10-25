from collections.abc import Callable
from pathlib import Path

import pytest

from foundry import session
from foundry.config import Project, Role
from foundry.session import SessionVariables
from foundry.task import Task


@pytest.fixture
def session_variables(tmp_path: Path) -> Callable[[Task], SessionVariables]:
    """The session variables a new sandbox for a task gets, from a real session under tmp_path/foundry.

    For a stand-in project and role: tests that need the variables, not a particular project.
    """

    def variables(task: Task) -> SessionVariables:
        opened = session.open_or_create(
            tmp_path / "foundry",
            project=Project(name="p", url="git@github.com:o/p.git"),
            role=Role(name="dev"),
            task=task,
        )
        return opened.variables

    return variables
