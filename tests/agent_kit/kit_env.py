"""The variables a sandbox's agent kit gets, for tests that run the kit's scripts.

Taken from a real session's sandbox definition, so the kit is tested with exactly the
names foundry sets, then pointed at this repository's agent kit and at checkouts under
the test's tmp_path.
"""

from pathlib import Path

from foundry import session
from foundry.config import Project, Role
from foundry.task import Task

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
PROJECT = Project(name="p", url="git@github.com:o/p.git")


def kit_env(tmp_path: Path, task: Task, *, role: str = "dev", **overrides: str) -> dict[str, str]:
    """The sandbox's variables for ``role`` on ``task``, with the checkouts under ``tmp_path/work``.

    ``overrides`` replace any variable, e.g. AGENT_REPO_URL for a local origin.
    """
    opened = session.open_or_create(tmp_path / "foundry", project=PROJECT, role=Role(name=role), task=task)
    return {
        **opened.definition.variables,
        "AGENT_KIT_DIR": str(AGENT_KIT_PATH),
        "AGENT_PROJECT_DIR": str(tmp_path / "work" / "p"),
        "AGENT_NOTES_DIR": str(tmp_path / "work" / "p-notes"),
        **overrides,
    }
