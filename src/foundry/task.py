"""Tasks on a project's repository: what a task's names are, creating one from the task template, and reading
its task state.

Task is the one place a task's names are spelled out. They reach the agent kit as session
variables (SessionVariables in session.py), so the kit derives none itself, and
tests/test_task_contract.py holds the kit, AGENTS.md and the rulesets to them.
"""

import re
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from agent_runtime.task.lifecycles import FEATURE, Lifecycle
from agent_runtime.task.state import TaskState, state_path
from foundry.errors import FoundryError
from foundry.project_clone import ProjectClone

# The branch holding every task's notes, each in its own dir (Task.task_notes_dir).
NOTES_BRANCH: Final = "agent-notes"
# Where every task's notes dir sits, on NOTES_BRANCH.
NOTES_ROOT: Final = ".agent"
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
    def task_notes_dir(self) -> str:
        """The task's notes dir on NOTES_BRANCH, relative to the repository root. Holds its TASK_FILE."""
        return f"{NOTES_ROOT}/{self.id}"

    @property
    def task_file(self) -> str:
        """The task's TASK_FILE on NOTES_BRANCH, relative to the repository root."""
        return f"{self.task_notes_dir}/{TASK_FILE}"

    @property
    def state_file(self) -> str:
        """The task's task state on NOTES_BRANCH, relative to the repository root."""
        return state_path(self.task_notes_dir)


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


def create(clone: ProjectClone, task: Task, template: Mapping[str, str], lifecycle: Lifecycle) -> None:
    """Create the task's branch from the default branch, copy ``template`` into its task notes dir, and start its task
    state in ``lifecycle``'s initial state.

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
    if clone.exists(task.task_notes_dir):
        raise FoundryError(f"task {task.id} already exists: {NOTES_BRANCH} has {task.task_notes_dir}/")
    clone.write({f"{task.task_notes_dir}/{name}": text for name, text in template.items()})
    clone.write({task.state_file: TaskState.new(lifecycle).to_json()})
    clone.commit(f"Add task {task.id}")
    clone.push_atomic(from_remote={task.branch: default_branch}, from_local=[NOTES_BRANCH])


_EXAMPLE_STATE: Final = TaskState(
    lifecycle=FEATURE, state="implement", previous=None, note="Started before task states: read PROGRESS.md."
)
"""What read_state suggests adding to a task created before task states."""


def task_ids(clone: ProjectClone) -> list[str]:
    """Every task's id on NOTES_BRANCH, sorted, from ``clone`` with it checked out."""
    return clone.dirs(NOTES_ROOT)


def read_state(clone: ProjectClone, task: Task) -> TaskState:
    """The task's task state, from ``clone`` with NOTES_BRANCH checked out.

    FoundryError if there is no such task, or it has no task state; TaskStateRefused if the file isn't one.
    """
    if not clone.exists(task.task_notes_dir):
        raise FoundryError(f"there is no task {task.id}. {NOTES_BRANCH} has no {task.task_notes_dir}/.")
    text = clone.read(task.state_file)
    if text is None:
        raise FoundryError(
            f"task {task.id} has no {task.state_file} on {NOTES_BRANCH}. It was created before task states. "
            f"Add it on {NOTES_BRANCH}, naming the lifecycle and the state it is in, for example:\n"
            + textwrap.indent(_EXAMPLE_STATE.to_json(), "  ")
        )
    return TaskState.parse(text, f"{task.state_file} on {NOTES_BRANCH}")
