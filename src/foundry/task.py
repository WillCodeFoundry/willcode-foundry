"""Tasks on a project's repository: what a task's names are, how the next task id is picked, and the task template.

Task is the one place a task's names are spelled out. They reach the agent kit as session
variables (session.session_variables), so the kit derives none itself, and
tests/test_task_contract.py holds the kit, AGENTS.md and the rulesets to them.
"""

import re
from collections import Counter
from collections.abc import Iterable
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
# The notes file the roles talk through, as numbered entries appended and never changed, as agent-kit/AGENTS.md
# says. The runtime's git hooks spell it too, as their own LOG_FILE.
LOG_FILE: Final = "LOG.md"

# Each task's branch is this, then its id (Task.branch).
BRANCH_PREFIX: Final = "task/"

# A task id: a task prefix of lowercase ASCII letters, '-', then a number of four or more digits, such as wcf-0042.
# It is also a valid ref component, so task/<id> is always a valid branch.
_TASK_ID = re.compile(r"(?P<task_prefix>[a-z]+)-(?P<number>[0-9]{4,})")


class Status(Enum):
    """Whether a task is in progress (open) or finished (closed)."""

    OPEN = auto()
    CLOSED = auto()


# Where each status keeps its tasks' notes dirs.
_STATUS_DIRS: Final = {Status.OPEN: OPEN_DIR, Status.CLOSED: CLOSED_DIR}


@dataclass(frozen=True)
class Task:
    """A task, named by its id and its status: Task("wcf-0042", Status.OPEN).

    The id must match _TASK_ID as given, never lowercased; otherwise FoundryError. ProjectTasks gives a task the
    status its repository says it has.
    """

    id: str
    status: Status

    def __post_init__(self) -> None:
        if not _TASK_ID.fullmatch(self.id):
            raise FoundryError(
                f"task id {self.id!r} is not valid: "
                "use lowercase letters, '-', then four or more digits (e.g. wcf-0042)"
            )

    @classmethod
    def as_open(cls, task_id: str) -> "Task":
        return cls(task_id, Status.OPEN)

    @classmethod
    def as_closed(cls, task_id: str) -> "Task":
        return cls(task_id, Status.CLOSED)

    @property
    def branch(self) -> str:
        """The task's branch, where the code is written."""
        return f"{BRANCH_PREFIX}{self.id}"

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

    @property
    def log_file(self) -> str:
        """The task's LOG_FILE on NOTES_BRANCH, relative to the repository root."""
        return f"{self.task_notes_dir}/{LOG_FILE}"


class NoNextTaskIdError(FoundryError):
    """No next task id can be picked: no task id is taken, or task prefixes tie for the most ids."""


def next_task_id(taken_ids: Iterable[str]) -> str:
    """The task id after ``taken_ids``: the task prefix most of them use, and one more than its highest number.

    Each id is counted once. Names that aren't task ids are ignored, and so are ids with other task prefixes. The
    number has at least four digits. NoNextTaskIdError when no task id is taken, or task prefixes tie for the most.
    """
    matches = [match for taken_id in set(taken_ids) if (match := _TASK_ID.fullmatch(taken_id))]
    task_prefixes = Counter(match["task_prefix"] for match in matches)
    if not task_prefixes:
        raise NoNextTaskIdError("the project repository has no task id to follow")
    most = max(task_prefixes.values())
    tied = sorted(task_prefix for task_prefix, count in task_prefixes.items() if count == most)
    if len(tied) > 1:
        raise NoNextTaskIdError(
            f"the project repository's task ids tie for the most common task prefix: {', '.join(tied)}"
        )
    task_prefix = tied[0]
    number = max(int(match["number"]) for match in matches if match["task_prefix"] == task_prefix) + 1
    return f"{task_prefix}-{number:04d}"


def load_task_template(task_template_dir: Path) -> dict[str, str]:
    """Every file directly in ``task_template_dir``, by name: what a new task's notes dir starts with.

    Refuses a template without a TASK_FILE, since every task needs one.
    """
    try:
        task_template = {path.name: path.read_text() for path in sorted(task_template_dir.iterdir()) if path.is_file()}
    except FileNotFoundError:
        raise FoundryError(f"{task_template_dir} is missing") from None
    if TASK_FILE not in task_template:
        raise FoundryError(f"{task_template_dir} has no {TASK_FILE}; every task needs one")
    return task_template
