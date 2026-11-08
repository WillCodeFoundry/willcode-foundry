"""ProjectTasks: the tasks of one project's repository: finding, creating, closing and reopening them, reading their
turn and handing them off, and listing the open ones with their turns.

The repository decides a task's status, by which dir under NOTES_ROOT holds its notes: get_task_by_id finds it, and
every operation on one task goes through it, and callers pass task ids. Listing is the exception: it reads every
dir under OPEN_DIR from one fetch, since get_task_by_id would fetch once per task.
"""

import re
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

from foundry.errors import FoundryError
from foundry.project_clone import PathNotOnBranchError, ProjectClone
from foundry.task import HUMAN, LOG_FILE, NOTES_BRANCH, OPEN_DIR, Status, Task

# A log entry's heading: "## <number> · <role> · <progress or outcome>", the number captured.
_LOG_HEADING = re.compile(r"## ([0-9]+) · ")


class TaskNotFoundError(FoundryError):
    """The task's notes dir is on neither side: it isn't open and it isn't closed."""


class ClosedTaskError(FoundryError):
    """The task is closed, so it can't change until it is reopened."""

    def __init__(self, task: Task) -> None:
        super().__init__(f"task {task.id} is closed")
        self.task = task


class MissingTurnError(FoundryError):
    """The task's TURN_FILE is missing, not a file, or holds only blanks."""

    def __init__(self, task: Task) -> None:
        super().__init__(f"task {task.id} has no turn: {NOTES_BRANCH} has no {task.turn_file}, or it is empty.")
        self.task = task


@dataclass(frozen=True)
class TaskTurn:
    """A task and whose turn it is: the stripped text of its TURN_FILE."""

    task: Task
    turn: str


class ProjectTasks:
    """The operations on a project's tasks, through its ProjectClone. Holds no state of its own."""

    def __init__(self, clone: ProjectClone) -> None:
        self._clone = clone

    @classmethod
    @contextmanager
    def in_scratch_clone(cls, url: str, env: Mapping[str, str]) -> Iterator["ProjectTasks"]:
        """The tasks of the repository at ``url``, through a clone in a temporary dir removed afterwards.

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
        open_candidate, closed_candidate = Task.as_open(task_id), Task.as_closed(task_id)
        open_dir, closed_dir = open_candidate.task_notes_dir, closed_candidate.task_notes_dir
        is_open, is_closed = clone.exists(open_dir), clone.exists(closed_dir)
        if is_open and is_closed:
            raise FoundryError(
                f"task {open_candidate.id} is both open and closed: {NOTES_BRANCH} has {open_dir}/ and {closed_dir}/"
            )
        if not is_open and not is_closed:
            raise TaskNotFoundError(
                f"task {open_candidate.id} doesn't exist: {NOTES_BRANCH} has neither {open_dir}/ nor {closed_dir}/"
            )
        return open_candidate if is_open else closed_candidate

    def create_task(self, task_id: str, task_template: Mapping[str, str]) -> Task:
        """Create the task's branch from the default branch, and copy ``task_template`` into its open notes dir.

        Both branches are pushed at once, so either both change or neither does. Refuses if the task exists, open
        or closed, or its branch does. NOTES_BRANCH is created for the first task, as an orphan branch: it shares
        no history with the code.
        """
        try:
            existing = self.get_task_by_id(task_id)
        except TaskNotFoundError:
            pass  # the id is free; get_task_by_id has checked out NOTES_BRANCH, or started it with no history
        else:
            raise FoundryError(f"task {existing.id} already exists: {NOTES_BRANCH} has {existing.task_notes_dir}/")
        clone = self._clone
        new_task = Task.as_open(task_id)
        default_branch = clone.default_branch()
        branches = clone.branches()
        if new_task.branch in branches:
            raise FoundryError(f"task {new_task.id} already exists: there is a {new_task.branch} branch")
        if default_branch is None or default_branch not in branches:  # a repository with no commits yet
            raise FoundryError(f"the repository has no commits to branch {new_task.branch} from")

        clone.write({f"{new_task.task_notes_dir}/{name}": text for name, text in task_template.items()})
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

        MissingTurnError when the file is missing, not a file or empty.
        """
        task = self.get_task_by_id(task_id)  # it fetched NOTES_BRANCH, if the task exists
        return self._read_fetched_turn(task)

    def hand_off(self, task_id: str, turn: str, *, note: str | None) -> None:
        """Hand the open task off to ``turn``, in one commit pushed to NOTES_BRANCH.

        Writes ``turn`` to the task's TURN_FILE, and an entry saying so to its LOG_FILE, with ``note`` when it isn't
        None. A task with no turn is handed off like any other. The caller checks ``turn``.

        FoundryError, with nothing pushed, when:
        - get_task_by_id refuses the task id, or the task is closed (ClosedTaskError);
        - its turn is already ``turn``;
        - it has no LOG_FILE;
        - its TURN_FILE or LOG_FILE is a link, as ProjectClone.write refuses.
        """
        task = self.get_task_by_id(task_id)
        if task.status is Status.CLOSED:
            raise ClosedTaskError(task)
        with suppress(MissingTurnError):
            if self._read_fetched_turn(task) == turn:
                raise FoundryError(f"task {task.id}'s turn is already {turn}")
        log = self._read_fetched_log(task)
        self._clone.write(
            {
                task.turn_file: f"{turn}\n",
                task.log_file: log_with_handoff_entry(log, turn=turn, note=note),
            }
        )
        self._commit_and_push(f"Handoff of task {task.id} to {turn}")

    def fetch_open_task_turns(self) -> list[TaskTurn]:
        """Every open task with whose turn it is, in id order; closed tasks and stray files are left out.

        Fetches NOTES_BRANCH once, then reads git objects. FoundryError when it isn't there, when a dir under
        OPEN_DIR isn't a valid task id, or when a task's TURN_FILE is missing, empty or not a file.
        """
        clone = self._clone
        clone.fetch_branch(NOTES_BRANCH)
        try:
            names = clone.fetched_subdir_names(NOTES_BRANCH, OPEN_DIR)
        except PathNotOnBranchError:
            return []  # git keeps no empty dir, so OPEN_DIR is gone once its last task closed
        tasks = [_open_task_for_dir(name) for name in sorted(names)]
        return [TaskTurn(task, self._read_fetched_turn(task)) for task in tasks]

    def _read_fetched_turn(self, task: Task) -> str:
        """``task``'s turn: its TURN_FILE on NOTES_BRANCH as last fetched, stripped.

        MissingTurnError when the file is missing, not a file, or holds only blanks.
        """
        try:
            turn = self._clone.fetched_text(NOTES_BRANCH, task.turn_file).strip()
        except PathNotOnBranchError:
            turn = ""
        if not turn:
            raise MissingTurnError(task)
        return turn

    def _read_fetched_log(self, task: Task) -> str:
        """``task``'s LOG_FILE on NOTES_BRANCH as last fetched; FoundryError, naming the file, when it is missing or
        not a file."""
        try:
            return self._clone.fetched_text(NOTES_BRANCH, task.log_file)
        except PathNotOnBranchError:
            raise FoundryError(
                f"task {task.id} has no {LOG_FILE}: {NOTES_BRANCH} has no file {task.log_file}"
            ) from None

    def _move(self, task: Task, destination: Task, *, message: str) -> Task:
        """Move ``task``'s notes dir to ``destination``'s, commit it with ``message``, and push NOTES_BRANCH.

        Relies on get_task_by_id having found ``task``: it checked out NOTES_BRANCH, so the move is made on the commit
        the task was found on.
        """
        self._clone.move_dir(task.task_notes_dir, destination.task_notes_dir)
        self._commit_and_push(message)
        return destination

    def _commit_and_push(self, message: str) -> None:
        """Commit every change in the checkout with ``message``, signed, and push NOTES_BRANCH."""
        self._clone.commit(message)
        self._clone.push_atomic(from_remote={}, from_local=[NOTES_BRANCH])


def _open_task_for_dir(dir_name: str) -> Task:
    """The open task whose notes dir is OPEN_DIR/``dir_name``; FoundryError, naming the dir, when ``dir_name`` isn't a
    task id as it stands."""
    try:
        return Task(dir_name, Status.OPEN)
    except FoundryError as error:
        raise FoundryError(f"{OPEN_DIR}/{dir_name}/ is not a valid task id ({error}). Rename or remove it.") from error


def log_with_handoff_entry(log: str, *, turn: str, note: str | None) -> str:
    """``log``, then a blank line and an entry saying you handed the task off to ``turn``.

    The log's text is kept, but for the whitespace at its end; a blank log gets no blank line. The entry is numbered
    one more than the last line that starts as a heading, or 1. Its Note line holds ``note`` stripped, and is left
    out when ``note`` is None.
    """
    numbers = [match[1] for line in log.split("\n") if (match := _LOG_HEADING.match(line))]
    number = int(numbers[-1]) + 1 if numbers else 1
    entry = [f"## {number} · {HUMAN} · handoff", f"Turn: {turn}."]
    if note is not None:
        entry.append(f"Note: {note.strip()}")
    kept = log.rstrip()
    return (f"{kept}\n\n" if kept else "") + "\n".join(entry) + "\n"
