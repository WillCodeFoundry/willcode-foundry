"""ProjectTasks: the tasks of one project's repository: finding, creating, closing and reopening them, reading their
turn and handing it on, and listing the open ones with their turns.

The repository decides a task's status, by which dir under NOTES_ROOT holds its notes: get_task_by_id finds it, and
every operation on one task goes through it. Callers pass task ids, and get Tasks back. hand_on_turn is the exception
that takes the Task get_task_by_id gave, so a caller can check it first without a second fetch. Listing is another:
it reads every dir under OPEN_DIR from one fetch, since get_task_by_id would fetch once per task.
"""

import re
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from foundry.errors import FoundryError
from foundry.project_clone import NotOnBranchError, ProjectClone
from foundry.task import HUMAN, LOG_FILE, NOTES_BRANCH, OPEN_DIR, Status, Task

# The turn a task has when its TURN_FILE is missing, empty or only blanks, as a hand-off names it.
_NO_TURN = "none"
# A log entry's heading: "## <number> · <role> · <progress or outcome>", the number captured.
_LOG_HEADING = re.compile(r"## ([0-9]+) · ")


class TaskNotFoundError(FoundryError):
    """The task's notes dir is on neither side: it isn't open and it isn't closed."""


@dataclass(frozen=True)
class TaskSummary:
    """A task and whose turn it is: the stripped text of its TURN_FILE."""

    task: Task
    turn: str


@dataclass(frozen=True)
class TurnChange:
    """A task whose turn you handed on: its turn ``before``, as hand_on_turn read it, and ``after``."""

    task: Task
    before: str
    after: str


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

        FoundryError when the file is missing, not a file or empty, saying to name the role instead.
        """
        task = self.get_task_by_id(task_id)  # it fetched NOTES_BRANCH, if the task exists
        return self._read_fetched_turn(task, fix="Name the role to run instead.")

    def hand_on_turn(self, task: Task, turn: str, *, note: str | None) -> TurnChange:
        """Write ``turn`` to the open ``task``'s TURN_FILE, and an entry saying so to its LOG_FILE, with ``note`` when
        it isn't None. One commit, pushed to NOTES_BRANCH.

        Relies on get_task_by_id having just found ``task`` open: it checked out NOTES_BRANCH, so the change is made
        on the commit the task was found on. The turn before is TURN_FILE's text stripped, or "none" when it is
        missing or blank. Refuses a task whose turn is already ``turn``, that has no LOG_FILE, or whose TURN_FILE or
        LOG_FILE is a link, as ProjectClone.write does. Checks nothing about ``turn``: the caller does.
        """
        assert task.status is Status.OPEN, "hand_on_turn needs an open task"  # a programming error
        before = self._read_fetched_turn_or_empty(task) or _NO_TURN
        if before == turn:
            raise FoundryError(f"task {task.id}'s turn is already {turn}")
        clone = self._clone
        try:
            log = clone.fetched_read(NOTES_BRANCH, task.log_file)
        except NotOnBranchError:
            raise FoundryError(
                f"task {task.id} has no {LOG_FILE}: {NOTES_BRANCH} has no file {task.log_file}"
            ) from None
        clone.write(
            {
                task.turn_file: f"{turn}\n",
                task.log_file: log_with_turn_entry(log, before=before, after=turn, note=note),
            }
        )
        clone.commit(f"Turn of task {task.id}: {before} → {turn}")
        clone.push_atomic(from_remote={}, from_local=[NOTES_BRANCH])
        return TurnChange(task, before=before, after=turn)

    def list_open_task_summaries(self) -> list[TaskSummary]:
        """Every open task with whose turn it is, in id order; closed tasks and stray files are left out.

        Fetches NOTES_BRANCH once, then reads git objects. FoundryError when it isn't there, when a dir under
        OPEN_DIR isn't a valid task id, or when a task's TURN_FILE is missing, empty or not a file.
        """
        clone = self._clone
        clone.fetch_branch(NOTES_BRANCH)
        try:
            names = clone.fetched_list_dir(NOTES_BRANCH, OPEN_DIR)
        except NotOnBranchError:
            return []  # git keeps no empty dir, so OPEN_DIR is gone once its last task closed
        tasks = [_open_task_for_dir(name) for name in sorted(names)]
        return [
            TaskSummary(task, self._read_fetched_turn(task, fix="Write the next role's name in it.")) for task in tasks
        ]

    def _read_fetched_turn(self, task: Task, *, fix: str) -> str:
        """``task``'s turn: its TURN_FILE on NOTES_BRANCH as last fetched, stripped.

        FoundryError, ending with ``fix``, when the file is missing, not a file, or holds only blanks.
        """
        turn = self._read_fetched_turn_or_empty(task)
        if not turn:
            raise FoundryError(
                f"task {task.id} has no turn: {NOTES_BRANCH} has no {task.turn_file}, or it is empty. {fix}"
            )
        return turn

    def _read_fetched_turn_or_empty(self, task: Task) -> str:
        """``task``'s TURN_FILE on NOTES_BRANCH as last fetched, stripped; empty when it is missing or not a file."""
        try:
            return self._clone.fetched_read(NOTES_BRANCH, task.turn_file).strip()
        except NotOnBranchError:
            return ""

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


def _open_task_for_dir(dir_name: str) -> Task:
    """The open task whose notes dir is OPEN_DIR/``dir_name``; FoundryError, naming the dir, when ``dir_name`` isn't a
    task id as it stands."""
    try:
        return Task(dir_name, Status.OPEN)
    except FoundryError as error:
        raise FoundryError(f"{OPEN_DIR}/{dir_name}/ is not a valid task id ({error}). Rename or remove it.") from error


def log_with_turn_entry(log: str, *, before: str, after: str, note: str | None) -> str:
    """``log``, unchanged, then a blank line and an entry saying you handed the turn from ``before`` to ``after``.

    The entry is numbered one more than the last line that starts as a heading, or 1. Its Note line holds ``note``
    stripped, and is left out when ``note`` is None. A newline is added after non-empty ``log`` that lacks one.
    """
    numbers = [match[1] for line in log.split("\n") if (match := _LOG_HEADING.match(line))]
    number = int(numbers[-1]) + 1 if numbers else 1
    entry = [f"## {number} · {HUMAN} · turn", f"Turn: {before} → {after}."]
    if note is not None:
        entry.append(f"Note: {note.strip()}")
    separator = "\n" if log and not log.endswith("\n") else ""
    return log + separator + "\n" + "\n".join(entry) + "\n"
