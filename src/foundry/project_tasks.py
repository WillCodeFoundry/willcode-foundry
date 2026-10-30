"""ProjectTasks: the tasks of one project's repository: creating, closing and reopening them, and reading their turn.

The repository decides a task's status, by which dir under NOTES_ROOT holds its notes. The Task a caller passes is
its expectation, so each operation checks the repository and refuses when it differs.
"""

from collections.abc import Mapping

from foundry.errors import FoundryError
from foundry.project_clone import ProjectClone
from foundry.task import NOTES_BRANCH, Status, Task


class ProjectTasks:
    """The operations on a project's tasks, through its ProjectClone. Holds no state of its own."""

    def __init__(self, clone: ProjectClone) -> None:
        self._clone = clone

    def create(self, task: Task, template: Mapping[str, str]) -> None:
        """Create the task's branch from the default branch, and copy ``template`` into its open notes dir.

        Both branches are pushed at once, so either both change or neither does. Refuses if the task
        exists, open or closed. NOTES_BRANCH is created for the first task, as an orphan branch: it shares no
        history with the code.
        """
        assert task.status is Status.OPEN, "a new task is open"  # a programming error
        clone = self._clone
        default_branch = clone.default_branch()
        branches = clone.branches()
        if task.branch in branches:
            raise FoundryError(f"task {task.id} already exists: there is a {task.branch} branch")
        if default_branch is None or default_branch not in branches:  # a repository with no commits yet
            raise FoundryError(f"the repository has no commits to branch {task.branch} from")

        clone.check_out(NOTES_BRANCH)  # started with no history if it doesn't exist: the first task creates it
        for status in Status:
            existing = Task(task.id, status).task_notes_dir
            if clone.exists(existing):
                raise FoundryError(f"task {task.id} already exists: {NOTES_BRANCH} has {existing}/")
        clone.write({f"{task.task_notes_dir}/{name}": text for name, text in template.items()})
        clone.commit(f"Add task {task.id}")
        clone.push_atomic(from_remote={task.branch: default_branch}, from_local=[NOTES_BRANCH])

    def close(self, task: Task) -> None:
        """Move the open task's notes dir to the closed ones, in one commit pushed to NOTES_BRANCH.

        Refuses a task that is already closed, or in neither.
        """
        assert task.status is Status.OPEN, "close takes an open task"  # a programming error
        self._move(task, Task.as_closed(task.id), commit=f"Close task {task.id}")

    def reopen(self, task: Task) -> None:
        """Move the closed task's notes dir back to the open ones, in one commit pushed to NOTES_BRANCH.

        Refuses a task that is already open, or in neither.
        """
        assert task.status is Status.CLOSED, "reopen takes a closed task"  # a programming error
        self._move(task, Task.as_open(task.id), commit=f"Reopen task {task.id}")

    def is_closed(self, task: Task) -> bool:
        """Whether NOTES_BRANCH holds the task's TASK_FILE under the closed dir."""
        return self._clone.read(NOTES_BRANCH, Task.as_closed(task.id).task_file) is not None

    def read_turn(self, task: Task) -> str:
        """Whose turn it is on the task, as its TURN_FILE on NOTES_BRANCH says: a role's name, or HUMAN.

        FoundryError when the file is missing or empty, saying to name the role instead.
        """
        text = self._clone.read(NOTES_BRANCH, task.turn_file)
        turn = text.strip() if text is not None else ""
        if not turn:
            raise FoundryError(
                f"task {task.id} has no turn: {NOTES_BRANCH} has no {task.turn_file}, or it is empty. "
                "Name the role to run instead."
            )
        return turn

    def _move(self, task: Task, destination: Task, *, commit: str) -> None:
        clone = self._clone
        clone.check_out(NOTES_BRANCH)
        # The two dirs are checked in the order the refusals go: the task's own status is the likelier mistake.
        if clone.exists(destination.task_notes_dir):
            raise FoundryError(f"task {task.id} is already {destination.status.name.lower()}")
        if not clone.exists(task.task_notes_dir):
            raise FoundryError(f"task {task.id} doesn't exist: {NOTES_BRANCH} has no {task.task_notes_dir}/")
        clone.move_dir(task.task_notes_dir, destination.task_notes_dir)
        clone.commit(commit)
        clone.push_atomic(from_remote={}, from_local=[NOTES_BRANCH])
