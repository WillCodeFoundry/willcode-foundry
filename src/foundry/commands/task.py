"""foundry task: create a task, launch whoever's turn it is, list every task's state, and move a task by hand.

Each subcommand's composition root builds the real config, clones and sandboxes, and passes them to a function
the tests call with their own.
"""

import argparse
import os
import sys
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from agent_runtime.task.lifecycles import DEFAULT, HUMAN, LIFECYCLES
from agent_runtime.task.state import TaskState, TaskStateRefused
from foundry import agent_sandbox, config, paths, session, task
from foundry.errors import FoundryError
from foundry.project_clone import ProjectClone
from foundry.runtime_build import build_runtime
from foundry.task import NOTES_BRANCH, Task

_PROJECT_HELP = "project name, as listed in config/foundry.yaml"
_TASK_HELP = "task id, e.g. wcf-0042"


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create tasks, launch their turns, list them, move them by hand")
    actions = parser.add_subparsers(dest="action", required=True)

    create = actions.add_parser(
        "create",
        help=f"create task/TASK from the default branch, and {task.NOTES_ROOT}/TASK/ on {NOTES_BRANCH} "
        "from config/task-template/, with its task state",
        description="Uses git, with your own access to the project's repository. Refuses a task that already exists.",
    )
    create.add_argument("project_name", metavar="PROJECT", help=_PROJECT_HELP)
    create.add_argument("task_id", metavar="TASK", help=_TASK_HELP)
    create.add_argument(
        "--lifecycle", choices=LIFECYCLES, default=DEFAULT, help=f"the lifecycle the task follows (default: {DEFAULT})"
    )
    create.set_defaults(func=create_main)

    run = actions.add_parser(
        "run",
        help="start or re-attach to the sandbox of the role whose turn it is",
        description=f"Reads the task's state from {NOTES_BRANCH} and launches the role whose turn it is. "
        "Refuses a task that is waiting for you, or done.",
    )
    run.add_argument("project_name", metavar="PROJECT", help=_PROJECT_HELP)
    run.add_argument("task_id", metavar="TASK", help=_TASK_HELP)
    run.set_defaults(func=run_main)

    listing = actions.add_parser(
        "list", help="every task of every project: its state, whose turn it is, its sandbox and its hand-off note"
    )
    listing.set_defaults(func=list_main)

    move = actions.add_parser(
        "move",
        help="move a task by hand to any state of its lifecycle",
        description=f"Commits the task state as you, signed, and pushes {NOTES_BRANCH}.",
    )
    move.add_argument("project_name", metavar="PROJECT", help=_PROJECT_HELP)
    move.add_argument("task_id", metavar="TASK", help=_TASK_HELP)
    move.add_argument("state", metavar="STATE", help="a state of the task's lifecycle")
    move.add_argument("--note", required=True, help="the hand-off note: what the next assignee should read first")
    move.set_defaults(func=move_main)


@contextmanager
def _scratch_clone(url: str) -> Iterator[ProjectClone]:
    """A throwaway clone of the project, made with your own git access, removed afterwards."""
    with tempfile.TemporaryDirectory(prefix="foundry-task-") as scratch_dir:
        yield ProjectClone.init(url, Path(scratch_dir), os.environ)


def _notes_clone(clone: ProjectClone) -> ProjectClone:
    clone.check_out(NOTES_BRANCH)
    return clone


# --- create ---------------------------------------------------------------------


def create_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, task template and repository, in a scratch clone."""
    foundry_root = paths.find_foundry_root()
    project = config.load(foundry_root).project(args.project_name)
    new_task = Task(args.task_id)
    template = task.load_template(paths.task_template_dir(foundry_root))
    with _scratch_clone(project.url) as clone:
        task.create(clone, new_task, template, LIFECYCLES[args.lifecycle])
    print("\n".join(report(project.name, new_task)))
    return 0


def report(project_name: str, new_task: Task) -> list[str]:
    return [
        f"created task {new_task.id} in {project_name}",
        f"run it with: foundry task run {project_name} {new_task.id}",
    ]


# --- run ------------------------------------------------------------------------


def run_main(args: argparse.Namespace) -> NoReturn:
    """Composition root: read the task state from origin, prepare the launch of whoever's turn it is, then hand
    over to sbx."""
    foundry_root = paths.find_foundry_root()
    project = config.load(foundry_root).project(args.project_name)
    the_task = Task(args.task_id)
    with _scratch_clone(project.url) as clone:
        task_state = task.read_state(_notes_clone(clone), the_task)
    role_name = whose_turn(task_state, project_name=project.name, task=the_task)
    launch = prepare_launch(foundry_root, project_name=project.name, role_name=role_name, task=the_task)
    print(f"==> turn:      {role_name}, in {task_state.state}", file=sys.stderr)
    if launch.created:
        print(f"==> session:   {launch.request.definition_dir} (new)", file=sys.stderr)
    agent_sandbox.launch(launch.request)


def whose_turn(task_state: TaskState, *, project_name: str, task: Task) -> str:
    """The role to launch; FoundryError, saying what to do, when the task is yours or done."""
    move = f"foundry task move {project_name} {task.id}"
    if task_state.turn is None:
        raise FoundryError(f"task {task.id} is {task_state.state}; to reopen it: {move} STATE --note …")
    if task_state.turn == HUMAN:
        came_from = f" (from {task_state.previous})" if task_state.previous else ""
        raise FoundryError(
            f"task {task.id} is waiting for you, in {task_state.state}{came_from}: {task_state.note or '(no note)'}\n"
            f"  once you've answered, hand it on: {move} {task_state.previous or 'STATE'} --note …"
        )
    return task_state.turn


@dataclass(frozen=True)
class Launch:
    """A launch ready to hand over: the request, and whether this launch created the session."""

    request: agent_sandbox.LaunchRequest
    created: bool


def prepare_launch(foundry_root: Path, *, project_name: str, role_name: str, task: Task) -> Launch:
    """Everything up to the hand-over: the session, created the first time, the agent runtime built into its
    kit, and the request to launch it. A failed build aborts."""
    foundry_config = config.load(foundry_root)
    project = foundry_config.project(project_name)
    role = foundry_config.role(role_name)
    opened = session.open_or_create(foundry_root, project=project, role=role, task=task)
    build_runtime(paths.agent_kit_dir(foundry_root))
    request = agent_sandbox.LaunchRequest(
        definition_dir=opened.dir,
        ssh_key_path=role.ssh_key_path,
        init_command=opened.init_command,
        github_token_path=role.github_token_path,
    )
    return Launch(request, opened.created)


# --- list -----------------------------------------------------------------------

_COLUMNS = ("PROJECT", "TASK", "LIFECYCLE", "STATE", "TURN", "SANDBOX", "NOTE")
_NONE = "—"


@dataclass(frozen=True)
class Row:
    """One task in `foundry task list`: its task state, or why it couldn't be read."""

    project: str
    task: str
    state: TaskState | None
    error: str | None = None


def read_rows(project_name: str, clone: ProjectClone) -> list[Row]:
    """A row per task on the project's NOTES_BRANCH, in id order; none if it has no NOTES_BRANCH yet."""
    if NOTES_BRANCH not in clone.branches():
        return []
    _notes_clone(clone)
    rows = []
    for task_id in task.task_ids(clone):
        try:
            rows.append(Row(project_name, task_id, task.read_state(clone, Task(task_id))))
        except (FoundryError, TaskStateRefused) as error:
            rows.append(Row(project_name, task_id, None, str(error)))
    return rows


def table(rows: Sequence[Row], live_sandboxes: set[str]) -> list[str]:
    """The lines `foundry task list` prints: a header, then a row per task, in aligned columns."""
    cells = [list(_COLUMNS), *(_cells(row, live_sandboxes) for row in rows)]
    widths = [max(len(line[column]) for line in cells) for column in range(len(_COLUMNS) - 1)]
    return [
        "  ".join([*(cell.ljust(width) for cell, width in zip(line, widths, strict=False)), line[-1]]).rstrip()
        for line in cells
    ]


def _cells(row: Row, live_sandboxes: set[str]) -> list[str]:
    if row.state is None:
        first_line = (row.error or "").splitlines()[0]
        return [row.project, row.task, _NONE, _NONE, _NONE, _NONE, f"error: {first_line}"]
    turn = row.state.turn
    if turn is None:
        who, sandbox = _NONE, _NONE
    elif turn == HUMAN:
        who, sandbox = "you", _NONE
    else:
        name = session.sandbox_name(role_name=turn, project_name=row.project, task=Task(row.task))
        who, sandbox = turn, "running" if name in live_sandboxes else _NONE
    note = row.state.note.splitlines()[0] if row.state.note.strip() else ""
    return [row.project, row.task, row.state.lifecycle.name, row.state.state, who, sandbox, note]


def list_main(args: argparse.Namespace) -> int:
    """Composition root: every configured project's tasks, from scratch clones, and this machine's sandboxes.
    Exits 1 if any task's state couldn't be read, after printing every row."""
    foundry_config = config.load(paths.find_foundry_root())
    rows: list[Row] = []
    for project in foundry_config.projects.values():
        with _scratch_clone(project.url) as clone:
            rows += read_rows(project.name, clone)
    if not rows:
        print("no tasks")
        return 0
    print("\n".join(table(rows, agent_sandbox.live_sandboxes())))
    return 1 if any(row.error for row in rows) else 0


# --- move -----------------------------------------------------------------------


@dataclass(frozen=True)
class Move:
    """A task's state before and after a move by hand."""

    before: TaskState
    after: TaskState


def move_task(clone: ProjectClone, the_task: Task, *, to: str, note: str) -> Move:
    """Move the task to ``to`` with a hand-off note, then commit (signed) and push NOTES_BRANCH alone.

    Nothing is committed if the move is refused.
    """
    before = task.read_state(_notes_clone(clone), the_task)
    after = before.moved(to, note)
    clone.write({the_task.state_file: after.to_json()})
    clone.commit(f"{the_task.id}: {before.state} → {after.state} (moved by hand)")
    clone.push_atomic(from_remote={}, from_local=[NOTES_BRANCH])
    return Move(before, after)


def move_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    the_task = Task(args.task_id)
    with _scratch_clone(project.url) as clone:
        moved = move_task(clone, the_task, to=args.state, note=args.note)
    print(f"moved task {the_task.id} from {moved.before.state} to {moved.after.state}")
    if moved.after.turn not in (None, HUMAN):
        print(f"run it with: foundry task run {project.name} {the_task.id}")
    return 0
