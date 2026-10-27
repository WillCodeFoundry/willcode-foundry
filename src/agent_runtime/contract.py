"""What the launcher and the runtime agree on: the session variables' names, and how the runtime is run.

The session variables are the AGENT_* variables a sandbox is created with. Their names are spelled out
here, once: foundry.session.SessionVariables keys its values with these constants, and the runtime reads
them back with ``read_environ``.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from agent_runtime.agent_kit import AgentKit

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
TASK_NOTES: Final = "AGENT_TASK_NOTES"
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
    TASK_NOTES,
    TASK_FILE,
)
"""Every session variable, in the order the sandbox definition lists them."""

PYTHON: Final = "/usr/bin/python3"
"""The interpreter every call into the runtime uses: the template's own, root-owned, never ``env python3``."""


def command(kit_dir: Path, *args: str) -> tuple[str, ...]:
    """A call into the runtime in ``kit_dir``. ``-I`` ignores PYTHONPATH, PYTHON* and user site-packages,
    so nothing the agent sets can shadow the package."""
    return (PYTHON, "-I", str(AgentKit(kit_dir).runtime), *args)


class MissingVariables(Exception):
    """Session variables a command needs are not set: it is running outside a foundry sandbox."""

    def __init__(self, names: list[str]) -> None:
        super().__init__(f"{', '.join(names)} not set; this runs inside a foundry sandbox, which sets them")
        self.names = names


@dataclass(frozen=True, kw_only=True)
class Environ:
    """The session variables, read from the environment."""

    role: str
    task: str
    kit_dir: Path
    repo_url: str
    project_dir: Path
    notes_dir: Path
    task_branch: str
    notes_branch: str
    notes_root: str
    task_notes: str
    task_file: str


def read_environ(environ: Mapping[str, str] | None = None) -> Environ:
    """Every session variable, from ``environ`` (os.environ by default).

    Raises MissingVariables naming every one that is unset or empty, not only the first.
    """
    env = os.environ if environ is None else environ
    _require(env, NAMES)
    return Environ(
        role=env[ROLE],
        task=env[TASK],
        kit_dir=Path(env[KIT_DIR]),
        repo_url=env[REPO_URL],
        project_dir=Path(env[PROJECT_DIR]),
        notes_dir=Path(env[NOTES_DIR]),
        task_branch=env[TASK_BRANCH],
        notes_branch=env[NOTES_BRANCH],
        notes_root=env[NOTES_ROOT],
        task_notes=env[TASK_NOTES],
        task_file=env[TASK_FILE],
    )


def _require(env: Mapping[str, str], names: tuple[str, ...]) -> None:
    missing = [name for name in names if not env.get(name)]
    if missing:
        raise MissingVariables(missing)
