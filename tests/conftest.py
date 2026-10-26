import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from foundry import session
from foundry.config import Project, Role
from foundry.runtime_build import build_runtime
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
            role=Role(name="dev", ssh_key_path=tmp_path / "secrets" / "ssh" / "dev", github_token_path=None),
            task=task,
        )
        return opened.variables

    return variables


AGENT_KIT_SOURCE = Path(__file__).parents[1] / "agent-kit"


@pytest.fixture(scope="session")
def built_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of this repository's agent kit with the runtime built into it, made once per test run.

    Tests that run the kit as delivered use it, so none of them writes into the repository's agent-kit/.build/.
    Read-only by agreement: a test that changes the kit makes its own copy.
    """
    kit = tmp_path_factory.mktemp("built") / "agent-kit"
    shutil.copytree(AGENT_KIT_SOURCE, kit, symlinks=True, ignore=shutil.ignore_patterns(".build"))
    build_runtime(kit)
    return kit
