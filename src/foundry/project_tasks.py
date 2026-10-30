"""ProjectTasks: the tasks of one project's repository: finding, creating, closing and reopening them, and reading
their turn.

The repository decides a task's status, by which dir under NOTES_ROOT holds its notes: get_task_by_id finds it, and
every other operation goes through it. Callers pass task ids, and get Tasks back.
"""

import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from foundry.errors import FoundryError
from foundry.project_clone import ProjectClone
from foundry.task import NOTES_BRANCH, Status, Task


class TaskNotFoundError(FoundryError):
    """The task's notes dir is on neither side: it isn't open and it isn't closed."""


class ProjectTasks:
    """The operations on a project's tasks, through its ProjectClone. Holds no state of its own."""

    def __init__(self, clone: ProjectClone) -> None:
        self._clone = clone

    @classmethod
    @contextmanager
    def in_scratch_clone(cls, url: str, env: Mapping[str, str]) -> Iterator["ProjectTasks"]:
        """The tasks of the repository at ``url``, through a clone in a temporary folder removed afterwards.

        ``env`` is the environment git runs in, as for ProjectClone.
        """
        with tempfile.TemporaryDirectory(prefix="foundry-clone-") as scratch_dir:
            yield cls(ProjectClone.init(url, Path(scratch_dir), env))

    def get_task_by_id(self, task_id: str) -> Task:
        """The task named ``task_id``, with the status of the dir on NOTES_BRANCH that holds its notes.

        Checks out NOTES_BRANCH. TaskNotFoundError when neither dir exists; FoundryError when both do.
        """
        clone = self._clone
        clone.check_out(NOTES_BRANCH)
        if_open, if_closed = Task.as_open(task_id), Task.as_closed(task_id)
        is_open, is_closed = clone.exists(if_open.task_notes_dir), clone.exists(if_closed.task_notes_dir)
        if is_open and is_closed:
            raise FoundryError(
                f"task {if_open.id} is both open and closed: {NOTES_BRANCH} has {if_open.task_notes_dir}/ "
                f"and {if_closed.task_notes_dir}/"
            )
        if not is_open and not is_closed:
            raise TaskNotFoundError(
                f"task {if_open.id} doesn't exist: {NOTES_BRANCH} has neither {if_open.task_notes_dir}/ "
                f"nor {if_closed.task_notes_dir}/"
            )
        return if_open if is_open else if_closed

    def create_task(self, task_id: str, template: Mapping[str, str]) -> Task:
        """Create the task's branch from the default branch, and copy ``template`` into its open notes dir.

        Both branches are pushed at once, so either both change or neither does. Refuses if the task exists, open
        or closed, or its branch does. NOTES_BRANCH is created for the first task, as an orphan branch: it shares
        no history with the code.
        """
        try:
            found = self.get_task_by_id(task_id)
        except TaskNotFoundError:
            pass  # the id is free; get_task_by_id has checked out NOTES_BRANCH, or started it with no history
        else:
            raise FoundryError(f"task {found.id} already exists: {NOTES_BRANCH} has {found.task_notes_dir}/")
        clone = self._clone
        new_task = Task.as_open(task_id)
        default_branch = clone.default_branch()
        branches = clone.branches()
        if new_task.branch in branches:
            raise FoundryError(f"task {new_task.id} already exists: there is a {new_task.branch} branch")
        if default_branch is None or default_branch not in branches:  # a repository with no commits yet
            raise FoundryError(f"the repository has no commits to branch {new_task.branch} from")

        clone.write({f"{new_task.task_notes_dir}/{name}": text for name, text in template.items()})
        clone.commit(f"Add task {new_task.id}")
        clone.push_atomic(from_remote={new_task.branch: default_branch}, from_local=[NOTES_BRANCH])
        return new_task

    def close_task(self, task_id: str) -> Task:
        """Move the open task's notes dir to the closed ones, in one commit pushed to NOTES_BRANCH.

        Refuses a task that is already closed, or doesn't exist.
        """
        task = self.get_task_by_id(task_id)
        if task.status is Status.CLOSED:
            raise FoundryError(f"task {task.id} is already closed")
        return self._move(task, Task.as_closed(task.id), message=f"Close task {task.id}")

    def reopen_task(self, task_id: str) -> Task:
        """Move the closed task's notes dir back to the open ones, in one commit pushed to NOTES_BRANCH.

        Refuses a task that is already open, or doesn't exist.
        """
        task = self.get_task_by_id(task_id)
        if task.status is Status.OPEN:
            raise FoundryError(f"task {task.id} is already open")
        return self._move(task, Task.as_open(task.id), message=f"Reopen task {task.id}")

    def read_task_turn(self, task_id: str) -> str:
        """Whose turn it is on the task, as its TURN_FILE on NOTES_BRANCH says: a role's name, or HUMAN.

        FoundryError when the file is missing or empty, saying to name the role instead.
        """
        task = self.get_task_by_id(task_id)
        text = self._clone.read(NOTES_BRANCH, task.turn_file)
        turn = text.strip() if text is not None else ""
        if not turn:
            raise FoundryError(
                f"task {task.id} has no turn: {NOTES_BRANCH} has no {task.turn_file}, or it is empty. "
                "Name the role to run instead."
            )
        return turn

    def _move(self, task: Task, destination: Task, *, message: str) -> Task:
        """Move ``task``'s notes dir to ``destination``'s, commit it with ``message``, and push NOTES_BRANCH.

        Relies on get_task_by_id having found ``task``: it checked out NOTES_BRANCH, so the move is made on the commit
        the task was found on.
        """
        clone = self._clone
        clone.move_dir(task.task_notes_dir, destination.task_notes_dir)
        clone.commit(message)
        clone.push_atomic(from_remote={}, from_local=[NOTES_BRANCH])
        return destination
