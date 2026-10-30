"""Tasks on a project's repository: what a task's names are, and the task template.

Task is the one place a task's names are spelled out. They reach the agent kit as session
variables (SessionVariables in session.py), so the kit derives none itself, and
tests/test_task_contract.py holds the kit, AGENTS.md and the rulesets to them.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Final

from foundry.errors import FoundryError

# The branch holding every task's notes, each in its own dir (Task.task_notes_dir).
NOTES_BRANCH: Final = "agent-notes"
# Where every task's notes dir sits, on NOTES_BRANCH.
NOTES_ROOT: Final = ".agent"
# Under NOTES_ROOT: the notes dirs of the open tasks, and of the closed ones (Status).
OPEN_DIR: Final = f"{NOTES_ROOT}/tasks/open"
CLOSED_DIR: Final = f"{NOTES_ROOT}/tasks/closed"
# The notes file every task has: what the task is, written by you, or by the planner once you approve its draft.
TASK_FILE: Final = "TASK.md"
# The notes file that says whose turn it is: a role's name, or HUMAN. The task template starts it; each role writes
# the next one when its turn ends, as agent-kit/AGENTS.md says.
TURN_FILE: Final = "TURN"
# The turn that no role takes: the task waits for you.
HUMAN: Final = "human"

# A task id becomes the git branch task/<id>, so it must be a valid ref
# component as well as readable: wcf-0042, fix-login.2. Matched after
# lowercasing.
_TASK_ID = re.compile(r"[a-z0-9][a-z0-9._-]*")


class Status(Enum):
    """Whether a task is in progress (open) or finished (closed)."""

    OPEN = auto()
    CLOSED = auto()


# Where each status keeps its tasks' notes dirs.
_STATUS_DIRS: Final = {Status.OPEN: OPEN_DIR, Status.CLOSED: CLOSED_DIR}


@dataclass(frozen=True)
class Task:
    """A task, named by its id and its status: Task.from_id_and_status("WCF-0042", Status.OPEN).

    The id must be lowercase and ASCII, letters, digits, '.', '_' or '-', and make a valid branch name; otherwise
    FoundryError. ProjectTasks gives a task the status its repository says it has.
    """

    id: str
    status: Status

    def __post_init__(self) -> None:
        if not _TASK_ID.fullmatch(self.id) or ".." in self.id or self.id.endswith((".", ".lock")):
            raise FoundryError(
                f"task id {self.id!r} is not valid: use letters, digits, '.', '_' and '-', "
                "starting with a letter or digit (e.g. wcf-0042)"
            )

    @classmethod
    def from_id_and_status(cls, task_id: str, status: Status) -> "Task":
        """The task named ``task_id``, lowercased if it is ASCII (a few other letters lowercase into ASCII ones, so
        a non-ASCII id is refused as it is)."""
        return cls(task_id.lower() if task_id.isascii() else task_id, status)

    @classmethod
    def as_open(cls, task_id: str) -> "Task":
        return cls.from_id_and_status(task_id, Status.OPEN)

    @classmethod
    def as_closed(cls, task_id: str) -> "Task":
        return cls.from_id_and_status(task_id, Status.CLOSED)

    @property
    def branch(self) -> str:
        """The task's branch, where the code is written."""
        return f"task/{self.id}"

    @property
    def task_notes_dir(self) -> str:
        """The task's notes dir on NOTES_BRANCH, relative to the repository root. Holds its TASK_FILE."""
        return f"{_STATUS_DIRS[self.status]}/{self.id}"

    @property
    def task_file(self) -> str:
        """The task's TASK_FILE on NOTES_BRANCH, relative to the repository root."""
        return f"{self.task_notes_dir}/{TASK_FILE}"

    @property
    def turn_file(self) -> str:
        """The task's TURN_FILE on NOTES_BRANCH, relative to the repository root."""
        return f"{self.task_notes_dir}/{TURN_FILE}"


def load_template(template_dir: Path) -> dict[str, str]:
    """Every file directly in ``template_dir``, by name: what a new task's notes dir starts with.

    Refuses a template without a TASK_FILE, since every task needs one.
    """
    try:
        template = {path.name: path.read_text() for path in sorted(template_dir.iterdir()) if path.is_file()}
    except FileNotFoundError:
        raise FoundryError(f"{template_dir} is missing") from None
    if TASK_FILE not in template:
        raise FoundryError(f"{template_dir} has no {TASK_FILE}; every task needs one")
    return template
