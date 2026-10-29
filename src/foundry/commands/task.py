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

from agent_runtime.task.lifecycles import DEFAULT, LIFECYCLES
from agent_runtime.task.state import TaskState, TaskStateRefused, commit_subject
from foundry import agent_sandbox, config, paths, session
from foundry.errors import FoundryError
from foundry.project_clone import ProjectClone
from foundry.runtime_build import build_runtime
from foundry.task import NOTES_BRANCH, NOTES_ROOT, Task, create, load_template, read_state, task_ids

_PROJECT_HELP = "project name, as listed in config/foundry.yaml"
_TASK_HELP = "task id, e.g. wcf-0042"


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create tasks, launch their turns, list them, move them by hand")
    actions = parser.add_subparsers(dest="action", required=True)

    creating = actions.add_parser(
        "create",
        help=f"create task/TASK from the default branch, and {NOTES_ROOT}/TASK/ on {NOTES_BRANCH} "
        "from config/task-template/, with its task state",
        description="Uses git, with your own access to the project's repository. Refuses a task that already exists.",
    )
    creating.add_argument("project_name", metavar="PROJECT", help=_PROJECT_HELP)
    creating.add_argument("task_id", metavar="TASK", help=_TASK_HELP)
    creating.add_argument(
        "--lifecycle", choices=LIFECYCLES, default=DEFAULT, help=f"the lifecycle the task follows (default: {DEFAULT})"
    )
    creating.set_defaults(func=create_main)

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
        "list", help="every task of every project: its state, its assignee, its sandbox and its hand-off note"
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


# --- create ---------------------------------------------------------------------


def create_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, task template and repository, in a scratch clone."""
    foundry_root = paths.find_foundry_root()
    project = config.load(foundry_root).project(args.project_name)
    task = Task(args.task_id)
    template = load_template(paths.task_template_dir(foundry_root))
    with _scratch_clone(project.url) as clone:
        create(clone, task, template, LIFECYCLES[args.lifecycle])
    print("\n".join(report(project.name, task)))
    return 0


def report(project_name: str, task: Task) -> list[str]:
    return [
        f"created task {task.id} in {project_name}",
        f"run it with: foundry task run {project_name} {task.id}",
    ]


# --- run ------------------------------------------------------------------------


def run_main(args: argparse.Namespace) -> NoReturn:
    """Composition root: read the task state from origin, prepare the launch of whoever's turn it is, then hand
    over to sbx."""
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(foundry_root)
    project = foundry_config.project(args.project_name)
    task = Task(args.task_id)
    with _scratch_clone(project.url) as clone:
        clone.check_out(NOTES_BRANCH)
        task_state = read_state(clone, task)
    role_name = whose_turn(task_state, project_name=project.name, task=task)
    launch = prepare_launch(foundry_root, foundry_config, project=project, role_name=role_name, task=task)
    print(f"==> turn:      {role_name}, in {task_state.state}", file=sys.stderr)
    if launch.created:
        print(f"==> session:   {launch.request.definition_dir} (new)", file=sys.stderr)
    agent_sandbox.launch(launch.request)


def whose_turn(task_state: TaskState, *, project_name: str, task: Task) -> str:
    """The role to launch; FoundryError, saying what to do, when the task is yours or done."""
    if task_state.role:
        return task_state.role
    move = f"foundry task move {project_name} {task.id}"
    if task_state.assigned_to_human:
        raise FoundryError(
            f"task {task.id} is waiting for you, in {task_state.state}: {task_state.note or '(no note)'}\n"
            f"  once you've answered, hand it on: {move} STATE --note …"
        )
    raise FoundryError(f"task {task.id} is {task_state.state}. To reopen it, run {move} STATE --note …")


@dataclass(frozen=True)
class Launch:
    """A launch ready to hand over: the request, and whether this launch created the session."""

    request: agent_sandbox.LaunchRequest
    created: bool


def prepare_launch(
    foundry_root: Path, foundry_config: config.Config, *, project: config.Project, role_name: str, task: Task
) -> Launch:
    """Everything up to the hand-over: the session, created the first time, the agent runtime built into its
    kit, and the request to launch it. A failed build aborts."""
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

_COLUMNS = ("PROJECT", "TASK", "LIFECYCLE", "STATE", "ASSIGNEE", "SANDBOX", "NOTE")
_NONE = "—"


@dataclass(frozen=True)
class Row:
    """One task in `foundry task list` whose task state could be read."""

    project: str
    task: Task
    task_state: TaskState


def read_rows(project_name: str, clone: ProjectClone) -> tuple[list[Row], list[str]]:
    """A row per task on the project's NOTES_BRANCH whose task state could be read, in id order, and the whole
    error for each one that couldn't. Neither, if the project has no NOTES_BRANCH yet."""
    if NOTES_BRANCH not in clone.branches():
        return [], []
    clone.check_out(NOTES_BRANCH)
    rows, errors = [], []
    for task_id in task_ids(clone):
        try:
            task = Task(task_id)
            rows.append(Row(project_name, task, read_state(clone, task)))
        except (FoundryError, TaskStateRefused) as error:
            errors.append(f"{project_name} {task_id}: {error}")
    return rows, errors


def table(rows: Sequence[Row], live_sandboxes: set[str]) -> list[str]:
    """The lines `foundry task list` prints: a header, then a row per task, in aligned columns."""
    cells = [list(_COLUMNS), *(_cells(row, live_sandboxes) for row in rows)]
    widths = [max(len(line[column]) for line in cells) for column in range(len(_COLUMNS) - 1)]
    return [
        "  ".join([*(cell.ljust(width) for cell, width in zip(line, widths, strict=False)), line[-1]]).rstrip()
        for line in cells
    ]


def _cells(row: Row, live_sandboxes: set[str]) -> list[str]:
    task_state = row.task_state
    role = task_state.role
    if role is None:
        who, sandbox = ("you" if task_state.assigned_to_human else _NONE), _NONE
    else:
        name = session.sandbox_name(role_name=role, project_name=row.project, task=row.task)
        who, sandbox = role, ("running" if name in live_sandboxes else _NONE)
    note = task_state.note.splitlines()[0] if task_state.note.strip() else ""
    return [row.project, row.task.id, task_state.lifecycle.name, task_state.state, who, sandbox, note]


def list_main(args: argparse.Namespace) -> int:
    """Composition root: every configured project's tasks, from scratch clones, and this machine's sandboxes.

    The table shows each task whose state could be read. Then each one that couldn't gets its whole error, on
    stderr, which says how to fix it, and the command exits 1.
    """
    foundry_config = config.load(paths.find_foundry_root())
    rows: list[Row] = []
    errors: list[str] = []
    for project in foundry_config.projects.values():
        with _scratch_clone(project.url) as clone:
            project_rows, project_errors = read_rows(project.name, clone)
        rows += project_rows
        errors += project_errors
    if rows:
        print("\n".join(table(rows, agent_sandbox.live_sandboxes())))
    elif not errors:
        print("no tasks")
    for error in errors:
        print(f"\n{error}", file=sys.stderr)
    return 1 if errors else 0


# --- move -----------------------------------------------------------------------


def move_task(clone: ProjectClone, task: Task, *, to: str, note: str) -> tuple[TaskState, TaskState]:
    """Move the task to ``to`` with a hand-off note, then commit (signed) and push NOTES_BRANCH alone; the task
    state before and after.

    Nothing is committed if the move is refused.
    """
    clone.check_out(NOTES_BRANCH)
    old = read_state(clone, task)
    moved = old.moved(to, note)
    clone.write({task.state_file: moved.to_json()})
    clone.commit(commit_subject(task.id, old.state, moved.state, "moved by hand"))
    clone.push_atomic(from_remote={}, from_local=[NOTES_BRANCH])
    return old, moved


def move_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    task = Task(args.task_id)
    with _scratch_clone(project.url) as clone:
        old, moved = move_task(clone, task, to=args.state, note=args.note)
    print(f"moved task {task.id} from {old.state} to {moved.state}")
    if moved.role:
        print(f"run it with: foundry task run {project.name} {task.id}")
    return 0
