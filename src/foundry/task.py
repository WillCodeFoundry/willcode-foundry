"""Tasks on a project's repository: what a task's names are, and creating one from the task template.

Task is the one place a task's names are spelled out in Python; agent-kit/lib/task.sh is its
equivalent in the agent kit, and tests/test_task_contract.py holds the two, and the rulesets, to
the same names.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from foundry.errors import FoundryError
from foundry.git_clone import GitClone

# The branch holding every task's notes, each in its own folder (Task.notes_dir).
NOTES_BRANCH: Final = "agent-notes"
# The notes file every task has: what the task is, written by you, or by the planner once you approve its draft.
TASK_FILE: Final = "TASK.md"

# A task id becomes the git branch task/<id>, so it must be a valid ref
# component as well as readable: wcf-0042, fix-login.2. Matched after
# lowercasing.
_TASK_ID = re.compile(r"[a-z0-9][a-z0-9._-]*")


@dataclass(frozen=True)
class Task:
    """A task, named by its id: Task("WCF-0042").id is "wcf-0042".

    The id must be ASCII; it is lowercased, then must be letters, digits, '.', '_' or '-' and make a
    valid branch name; otherwise FoundryError.
    """

    id: str

    def __post_init__(self) -> None:
        # ASCII first: lower() turns a few other letters into ASCII ones (the Kelvin sign into k).
        lowered = self.id.lower() if self.id.isascii() else ""
        if not _TASK_ID.fullmatch(lowered) or ".." in lowered or lowered.endswith((".", ".lock")):
            raise FoundryError(
                f"task id {self.id!r} is not valid: use letters, digits, '.', '_' and '-', "
                "starting with a letter or digit (e.g. wcf-0042)"
            )
        object.__setattr__(self, "id", lowered)

    @property
    def branch(self) -> str:
        """The task's branch, where the code is written."""
        return f"task/{self.id}"

    @property
    def notes_dir(self) -> str:
        """The task's notes folder on NOTES_BRANCH, relative to the repository root. Holds its TASK_FILE."""
        return f".agent/{self.id}"


def load_template(template_dir: Path) -> dict[str, str]:
    """Every file directly in ``template_dir``, by name: what a new task's notes folder starts with.

    Refuses a template without a TASK_FILE, since every task needs one.
    """
    try:
        template = {path.name: path.read_text() for path in sorted(template_dir.iterdir()) if path.is_file()}
    except FileNotFoundError:
        raise FoundryError(f"{template_dir} is missing") from None
    if TASK_FILE not in template:
        raise FoundryError(f"{template_dir} has no {TASK_FILE}; every task needs one")
    return template


def create(clone: GitClone, task: Task, template: Mapping[str, str]) -> None:
    """Create the task's branch from the default branch, and copy ``template`` into its notes folder.

    Both branches are pushed at once, so either both change or neither does. Refuses if the task
    exists. NOTES_BRANCH is created for the first task, as an orphan branch: it shares no history
    with the code.
    """
    default_branch = clone.default_branch()
    branches = clone.branches()
    if task.branch in branches:
        raise FoundryError(f"task {task.id} already exists: there is a {task.branch} branch")
    if default_branch is None or default_branch not in branches:  # a repository with no commits yet
        raise FoundryError(f"the repository has no commits to branch {task.branch} from")

    clone.check_out(NOTES_BRANCH)  # started with no history if it doesn't exist: the first task creates it
    if clone.exists(task.notes_dir):
        raise FoundryError(f"task {task.id} already exists: {NOTES_BRANCH} has {task.notes_dir}/")
    clone.write({f"{task.notes_dir}/{name}": text for name, text in template.items()})
    clone.commit(f"Add task {task.id}")
    clone.push_atomic(from_remote={task.branch: default_branch}, from_local=[NOTES_BRANCH])
