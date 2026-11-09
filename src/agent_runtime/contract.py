"""What the launcher and the runtime agree on: the session variables' names, and the sandbox's user.

The session variables are the AGENT_* variables a sandbox is created with. Their names are spelled out
here, once, with the one class that holds their values: foundry.session builds a SessionVariables and writes
it with ``to_env``, and the runtime reads it back with ``read_session_variables``.
"""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROLE: Final = "AGENT_ROLE"
TASK_ID: Final = "AGENT_TASK_ID"
KIT_DIR: Final = "AGENT_KIT_DIR"
REPO_URL: Final = "AGENT_REPO_URL"
CODE_CHECKOUT_DIR: Final = "AGENT_CODE_CHECKOUT_DIR"
NOTES_CHECKOUT_DIR: Final = "AGENT_NOTES_CHECKOUT_DIR"
# A task's names, so the kit and the agent's instructions spell none out. The notes paths are
# relative to a checkout's root, as git reports paths.
TASK_BRANCH: Final = "AGENT_TASK_BRANCH"
NOTES_BRANCH: Final = "AGENT_NOTES_BRANCH"
NOTES_ROOT: Final = "AGENT_NOTES_ROOT"
TASK_NOTES_DIR: Final = "AGENT_TASK_NOTES_DIR"
TASK_FILE: Final = "AGENT_TASK_FILE"

NAMES: Final = (
    ROLE,
    TASK_ID,
    KIT_DIR,
    REPO_URL,
    CODE_CHECKOUT_DIR,
    NOTES_CHECKOUT_DIR,
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
class SessionVariables:
    """The session variables, one field per variable: foundry writes them, and the runtime reads them back.

    Each field is its variable's name, lowercased in full.
    """

    agent_role: str
    agent_task_id: str
    agent_kit_dir: Path
    agent_repo_url: str
    agent_code_checkout_dir: Path
    agent_notes_checkout_dir: Path
    agent_task_branch: str
    agent_notes_branch: str
    agent_notes_root: str
    agent_task_notes_dir: str
    agent_task_file: str

    def to_env(self) -> dict[str, str]:
        """The variables by name, in NAMES' order, as the sandbox definition carries them.

        ``read_session_variables(v.to_env()) == v``.
        """
        return {name: str(getattr(self, name.lower())) for name in NAMES}


def read_session_variables(variables: Mapping[str, str] | None = None) -> SessionVariables:
    """Every session variable, from ``variables`` (os.environ by default).

    Raises MissingVariables naming every one that is unset or empty.
    """
    variables = os.environ if variables is None else variables
    require_set(variables, NAMES)
    return SessionVariables(
        agent_role=variables[ROLE],
        agent_task_id=variables[TASK_ID],
        agent_kit_dir=Path(variables[KIT_DIR]),
        agent_repo_url=variables[REPO_URL],
        agent_code_checkout_dir=Path(variables[CODE_CHECKOUT_DIR]),
        agent_notes_checkout_dir=Path(variables[NOTES_CHECKOUT_DIR]),
        agent_task_branch=variables[TASK_BRANCH],
        agent_notes_branch=variables[NOTES_BRANCH],
        agent_notes_root=variables[NOTES_ROOT],
        agent_task_notes_dir=variables[TASK_NOTES_DIR],
        agent_task_file=variables[TASK_FILE],
    )


def require_set(variables: Mapping[str, str], names: Sequence[str]) -> None:
    """Raise MissingVariables naming every one of ``names`` that is unset or empty, not only the first."""
    if missing := missing_names(variables, names):
        raise MissingVariables(f"{', '.join(missing)} not set; this runs inside a foundry sandbox, which sets them")


def missing_names(variables: Mapping[str, str], names: Sequence[str]) -> list[str]:
    """Those of ``names`` that are unset or empty in ``variables``, in ``names``' order."""
    return [name for name in names if not variables.get(name)]
