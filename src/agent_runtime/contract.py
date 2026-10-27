"""What the launcher and the runtime agree on: the session variables' names, and the sandbox's user.

The session variables are the AGENT_* variables a sandbox is created with. Their names are spelled out
here, once: foundry.session.SessionVariables keys its values with these constants, and the runtime reads
them back with ``read_environ``.
"""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROLE: Final = "AGENT_ROLE"
TASK: Final = "AGENT_TASK"
KIT_DIR: Final = "AGENT_KIT_DIR"
REPO_URL: Final = "AGENT_REPO_URL"
PROJECT_DIR: Final = "AGENT_PROJECT_DIR"
NOTES_DIR: Final = "AGENT_NOTES_DIR"
# A task's names, so the kit and the agent's instructions spell none out. The notes paths are
# relative to a checkout's root, as git reports paths.
TASK_BRANCH: Final = "AGENT_TASK_BRANCH"
NOTES_BRANCH: Final = "AGENT_NOTES_BRANCH"
NOTES_ROOT: Final = "AGENT_NOTES_ROOT"
TASK_NOTES_DIR: Final = "AGENT_TASK_NOTES_DIR"
TASK_FILE: Final = "AGENT_TASK_FILE"

NAMES: Final = (
    ROLE,
    TASK,
    KIT_DIR,
    REPO_URL,
    PROJECT_DIR,
    NOTES_DIR,
    TASK_BRANCH,
    NOTES_BRANCH,
    NOTES_ROOT,
    TASK_NOTES_DIR,
    TASK_FILE,
)
"""Every session variable, in the order the sandbox definition lists them."""

SANDBOX_USER: Final = "agent"
"""The sandbox template's user, whom the agent runs as: root mode runs only through sudo from it, and the
checkouts sit in its home."""


class MissingVariables(Exception):
    """Session variables a command needs are not set: it is running outside a foundry sandbox."""


@dataclass(frozen=True, kw_only=True)
class Environ:
    """The session variables, read from the environment."""

    agent_role: str
    agent_task: str
    agent_kit_dir: Path
    agent_repo_url: str
    agent_project_dir: Path
    agent_notes_dir: Path
    agent_task_branch: str
    agent_notes_branch: str
    agent_notes_root: str
    agent_task_notes_dir: str
    agent_task_file: str


def read_environ(variables: Mapping[str, str] | None = None) -> Environ:
    """Every session variable, from ``variables`` (os.environ by default). Each field is its variable's name,
    lowercased in full.

    Raises MissingVariables naming every one that is unset or empty.
    """
    variables = os.environ if variables is None else variables
    require(variables, NAMES)
    return Environ(
        agent_role=variables[ROLE],
        agent_task=variables[TASK],
        agent_kit_dir=Path(variables[KIT_DIR]),
        agent_repo_url=variables[REPO_URL],
        agent_project_dir=Path(variables[PROJECT_DIR]),
        agent_notes_dir=Path(variables[NOTES_DIR]),
        agent_task_branch=variables[TASK_BRANCH],
        agent_notes_branch=variables[NOTES_BRANCH],
        agent_notes_root=variables[NOTES_ROOT],
        agent_task_notes_dir=variables[TASK_NOTES_DIR],
        agent_task_file=variables[TASK_FILE],
    )


def require(variables: Mapping[str, str], names: Sequence[str]) -> None:
    """Raise MissingVariables naming every one of ``names`` that is unset or empty, not only the first."""
    if missing := [name for name in names if not variables.get(name)]:
        raise MissingVariables(f"{', '.join(missing)} not set; this runs inside a foundry sandbox, which sets them")
