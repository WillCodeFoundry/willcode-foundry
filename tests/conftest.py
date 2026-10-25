from collections.abc import Callable
from pathlib import Path

import pytest

from foundry import session
from foundry.config import Project, Role
from foundry.task import Task


@pytest.fixture
def sandbox_variables(tmp_path: Path) -> Callable[[Task], dict[str, str]]:
    """The variables a new sandbox for a task gets, from a real session under tmp_path/foundry.

    For a stand-in project and role: tests that need the variables, not a particular project.
    """

    def variables(task: Task) -> dict[str, str]:
        opened = session.open_or_create(
            tmp_path / "foundry",
            project=Project(name="p", url="git@github.com:o/p.git"),
            role=Role(name="dev"),
            task=task,
        )
        return dict(opened.definition.variables)

    return variables
