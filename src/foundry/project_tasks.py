"""ProjectTasks: the tasks of one project repository: finding, creating, closing and reopening them, reading their
turn and handing them off, and listing the open ones with their turns.

The project repository decides a task's status, by which dir under NOTES_ROOT holds its notes: fetch_task finds it,
every operation on one task goes through it, and callers pass task ids. There are two exceptions:
- Listing reads every dir under OPEN_DIR from one fetch, since fetch_task would fetch once per task.
- create_next_task takes no id. It reads the dirs under OPEN_DIR and CLOSED_DIR from one fetch of NOTES_BRANCH, and
  the task branches from the remote's branch list.

Finding and reading only fetch NOTES_BRANCH and read what was fetched: they change no file. An operation that writes
checks out the fetched NOTES_BRANCH itself, after every check that can refuse it, so it writes on what it read.
"""

import re
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

from foundry.errors import FoundryError
from foundry.project_scratch_clone import BranchNotFoundError, FetchedBranch, PathNotOnBranchError, ProjectScratchClone
from foundry.task import BRANCH_PREFIX, CLOSED_DIR, HUMAN, LOG_FILE, NOTES_BRANCH, OPEN_DIR, Status, Task, next_task_id

# A log entry's heading: "## <number> · <role> · <progress or outcome>", the number captured.
_LOG_HEADING = re.compile(r"## ([0-9]+) · ")


class TaskNotFoundError(FoundryError):
    """The task's notes dir is on neither side: it isn't open and it isn't closed."""


class ClosedTaskError(FoundryError):
    """The task is closed, so it can't change until it is reopened."""

    def __init__(self, task: Task) -> None:
        super().__init__(f"task {task.id} is closed")


class MissingTurnError(FoundryError):
    """The task's TURN_FILE is missing, not a file, or holds only blanks."""

    def __init__(self, task: Task) -> None:
        super().__init__(f"task {task.id} has no turn: {NOTES_BRANCH} has no {task.turn_file}, or it is empty.")


@dataclass(frozen=True)
class TaskTurn:
    """A task and whose turn it is: the stripped text of its TURN_FILE."""

    task: Task
    turn: str


class ProjectTasks:
    """The operations on a project's tasks, through its ProjectScratchClone. Holds no state of its own."""

    def __init__(self, clone: ProjectScratchClone) -> None:
        self._clone = clone

    @classmethod
    @contextmanager
    def in_scratch_clone(cls, url: str, env: Mapping[str, str]) -> Iterator["ProjectTasks"]:
        """The tasks of the project repository at ``url``, through a scratch clone removed afterwards.

        ``env`` is the environment git runs in, as for ProjectScratchClone.
        """
        with tempfile.TemporaryDirectory(prefix="foundry-clone-") as scratch_dir:
            yield cls(ProjectScratchClone.init(url, Path(scratch_dir), env))

    def fetch_task(self, task_id: str) -> Task:
        """The task named ``task_id``, with the status of the dir on NOTES_BRANCH that holds its notes.

        Fetches NOTES_BRANCH and reads it; changes no file. TaskNotFoundError when neither dir exists; FoundryError
        when both do. BranchNotFoundError when the project repository has no NOTES_BRANCH yet.
        """
        return _read_task(self._clone.fetch_branch(NOTES_BRANCH), task_id)

    def create_task(self, task_id: str, task_template: Mapping[str, str]) -> Task:
        """Create the task's branch from the default branch, and copy ``task_template`` into its open notes dir.

        Both branches are pushed at once, so either both change or neither does. Refuses if the task exists, open
        or closed, or its branch does. NOTES_BRANCH is created for the first task, as an orphan branch: it shares
        no history with the code. create_next_task picks the id instead.
        """
        return self._create(task_template, task_id=task_id)

    def create_next_task(self, task_template: Mapping[str, str]) -> Task:
        """Create the project's next task, as create_task does, under the id next_task_id picks from the taken ones.

        A task id is taken by an open or closed task's notes dir, or by a task branch. They are read once, and the
        task is written on what was read. NoNextTaskIdError, with nothing written or pushed, when no id can be
        picked. A create that picked the same id and pushed first makes this one's push fail, as GitError.
        """
        return self._create(task_template, task_id=None)

    def _create(self, task_template: Mapping[str, str], *, task_id: str | None) -> Task:
        """create_task with ``task_id``; given None, create_next_task."""
        clone = self._clone
        given_task = None if task_id is None else Task.as_open(task_id)  # refuses an invalid id before git runs
        branches, default_branch = clone.branches(), clone.default_branch()
        notes_branch = clone.fetch_branch(NOTES_BRANCH) if NOTES_BRANCH in branches else None  # None: the first task
        new_task = given_task or Task.as_open(next_task_id(_taken_task_ids(branches, notes_branch)))
        if notes_branch is not None:
            _require_no_task(notes_branch, new_task.id)  # first, as its message says whether the task is closed
        if new_task.branch in branches:
            raise FoundryError(f"task {new_task.id} already exists: there is a {new_task.branch} branch")
        if default_branch is None or default_branch not in branches:  # a project repository with no commits yet
            raise FoundryError(f"the project repository has no commits to branch {new_task.branch} from")
        if notes_branch is None:
            clone.start_orphan(NOTES_BRANCH)
        else:
            clone.check_out(notes_branch)
        clone.write({f"{new_task.task_notes_dir}/{name}": text for name, text in task_template.items()})
        clone.commit(f"Add task {new_task.id}")
        clone.push_atomic(from_remote={new_task.branch: default_branch}, from_local=[NOTES_BRANCH])
        return new_task

    def close_task(self, task_id: str) -> Task:
        """Move the open task's notes dir to the closed ones, in one commit pushed to NOTES_BRANCH.

        Refuses a task that is already closed, or doesn't exist.
        """
        notes_branch = self._clone.fetch_branch(NOTES_BRANCH)
        task = _read_task(notes_branch, task_id)
        if task.status is Status.CLOSED:
            raise FoundryError(f"task {task.id} is already closed")
        self._clone.check_out(notes_branch)
        return self._move(task, Task.as_closed(task.id), message=f"Close task {task.id}")

    def reopen_task(self, task_id: str) -> Task:
        """Move the closed task's notes dir back to the open ones, in one commit pushed to NOTES_BRANCH.

        Refuses a task that is already open, or doesn't exist.
        """
        notes_branch = self._clone.fetch_branch(NOTES_BRANCH)
        task = _read_task(notes_branch, task_id)
        if task.status is Status.OPEN:
            raise FoundryError(f"task {task.id} is already open")
        self._clone.check_out(notes_branch)
        return self._move(task, Task.as_open(task.id), message=f"Reopen task {task.id}")

    def fetch_task_turn(self, task_id: str) -> str:
        """Whose turn it is on the task, as its TURN_FILE on NOTES_BRANCH says: a role's name, or HUMAN.

        Fetches NOTES_BRANCH and reads it; changes no file. MissingTurnError when the file is missing, not a file
        or empty.
        """
        notes_branch = self._clone.fetch_branch(NOTES_BRANCH)
        return _read_turn(notes_branch, _read_task(notes_branch, task_id))

    def hand_off(self, task_id: str, turn: str, *, note: str | None) -> None:
        """Hand the open task off to ``turn``, in one commit pushed to NOTES_BRANCH.

        Writes ``turn`` to the task's TURN_FILE, and an entry saying so to its LOG_FILE, with ``note`` when it isn't
        None. A task with no turn is handed off like any other. The caller checks ``turn``.

        Every check reads the fetched NOTES_BRANCH; only then is it checked out, so the handoff is written on what
        was read. FoundryError, with nothing written or pushed, when:
        - fetch_task refuses the task id, or the task is closed (ClosedTaskError);
        - its turn is already ``turn``;
        - it has no LOG_FILE;
        - its TURN_FILE or LOG_FILE is a link, as ProjectScratchClone.write refuses.
        """
        notes_branch = self._clone.fetch_branch(NOTES_BRANCH)
        task = _read_task(notes_branch, task_id)
        if task.status is Status.CLOSED:
            raise ClosedTaskError(task)
        with suppress(MissingTurnError):
            if _read_turn(notes_branch, task) == turn:
                raise FoundryError(f"task {task.id}'s turn is already {turn}")
        log = _read_log(notes_branch, task)
        self._clone.check_out(notes_branch)
        self._clone.write(
            {
                task.turn_file: f"{turn}\n",
                task.log_file: log_with_handoff_entry(log, turn=turn, note=note),
            }
        )
        self._commit_and_push(f"Handoff of task {task.id} to {turn}")

    def fetch_open_task_turns(self) -> list[TaskTurn]:
        """Every open task with whose turn it is, in id order; closed tasks and stray files are left out.

        Fetches NOTES_BRANCH once, then reads what was fetched; changes no file. Empty when the project repository
        has no NOTES_BRANCH yet, as before its first task. FoundryError when a dir under OPEN_DIR isn't a valid task
        id, or when a task's TURN_FILE is missing, empty or not a file.
        """
        try:
            notes_branch = self._clone.fetch_branch(NOTES_BRANCH)
        except BranchNotFoundError:
            return []  # no task has been created yet
        tasks = [_open_task_for_dir(name) for name in sorted(_read_task_ids(notes_branch, OPEN_DIR))]
        return [TaskTurn(task, _read_turn(notes_branch, task)) for task in tasks]

    def _move(self, task: Task, destination: Task, *, message: str) -> Task:
        """Move ``task``'s notes dir to ``destination``'s, commit it with ``message``, and push NOTES_BRANCH.

        The caller has checked out NOTES_BRANCH, at the commit it found ``task`` on.
        """
        self._clone.move_dir(task.task_notes_dir, destination.task_notes_dir)
        self._commit_and_push(message)
        return destination

    def _commit_and_push(self, message: str) -> None:
        """Commit every change in the checkout with ``message``, signed, and push NOTES_BRANCH."""
        self._clone.commit(message)
        self._clone.push_atomic(from_remote={}, from_local=[NOTES_BRANCH])


def _read_task(notes_branch: FetchedBranch, task_id: str) -> Task:
    """The task named ``task_id``, with the status of the dir on ``notes_branch`` that holds its notes.

    TaskNotFoundError when neither dir exists; FoundryError when both do.
    """
    open_candidate, closed_candidate = Task.as_open(task_id), Task.as_closed(task_id)
    open_dir, closed_dir = open_candidate.task_notes_dir, closed_candidate.task_notes_dir
    is_open = open_candidate.id in _read_task_ids(notes_branch, OPEN_DIR)
    is_closed = closed_candidate.id in _read_task_ids(notes_branch, CLOSED_DIR)
    if is_open and is_closed:
        raise FoundryError(
            f"task {open_candidate.id} is both open and closed: {NOTES_BRANCH} has {open_dir}/ and {closed_dir}/"
        )
    if not is_open and not is_closed:
        raise TaskNotFoundError(
            f"task {open_candidate.id} doesn't exist: {NOTES_BRANCH} has neither {open_dir}/ nor {closed_dir}/"
        )
    return open_candidate if is_open else closed_candidate


def _require_no_task(notes_branch: FetchedBranch, task_id: str) -> None:
    """Refuse ``task_id`` if ``notes_branch`` holds its notes dir, open or closed."""
    try:
        existing = _read_task(notes_branch, task_id)
    except TaskNotFoundError:
        return
    raise FoundryError(f"task {existing.id} already exists: {NOTES_BRANCH} has {existing.task_notes_dir}/")


def _taken_task_ids(branches: list[str], notes_branch: FetchedBranch | None) -> set[str]:
    """The names that take a task id, valid or not.

    They are the dirs under OPEN_DIR and CLOSED_DIR on ``notes_branch`` (none when it is None), and each of
    ``branches`` starting with BRANCH_PREFIX, with BRANCH_PREFIX cut off.
    """
    taken = {branch.removeprefix(BRANCH_PREFIX) for branch in branches if branch.startswith(BRANCH_PREFIX)}
    if notes_branch is not None:
        taken |= {*_read_task_ids(notes_branch, OPEN_DIR), *_read_task_ids(notes_branch, CLOSED_DIR)}
    return taken


def _read_task_ids(notes_branch: FetchedBranch, status_dir: str) -> list[str]:
    """The names of the dirs under ``status_dir`` on ``notes_branch``: the ids of its tasks."""
    try:
        return notes_branch.subdir_names(status_dir)
    except PathNotOnBranchError:
        return []  # git keeps no empty dir, so a status dir is gone once its last task leaves


def _read_turn(notes_branch: FetchedBranch, task: Task) -> str:
    """``task``'s turn: its TURN_FILE on ``notes_branch``, stripped.

    MissingTurnError when the file is missing, not a file, or holds only blanks.
    """
    try:
        turn = notes_branch.read_text(task.turn_file).strip()
    except PathNotOnBranchError:
        turn = ""
    if not turn:
        raise MissingTurnError(task)
    return turn


def _read_log(notes_branch: FetchedBranch, task: Task) -> str:
    """``task``'s LOG_FILE on ``notes_branch``; FoundryError, naming the file, when it is missing or not a file."""
    try:
        return notes_branch.read_text(task.log_file)
    except PathNotOnBranchError:
        raise FoundryError(f"task {task.id} has no {LOG_FILE}: {NOTES_BRANCH} has no file {task.log_file}") from None


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
