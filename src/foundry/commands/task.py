"""foundry task: everything done to one task, each subcommand taking PROJECT TASK first.

create makes the task; run launches a role on it, and next the role whose turn it is; list shows
where every task stands.
"""

import argparse
import os
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session, task, task_state
from foundry.errors import FoundryError
from foundry.git_clone import GitClone
from foundry.task import Task
from foundry.task_state import HUMAN, Lifecycle, TaskState

_PROJECT_HELP = "project name, as listed in config/foundry.yaml"
_TASK_HELP = "task id, e.g. wcf-0042"


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create, run and list tasks")
    actions = parser.add_subparsers(dest="action", required=True)

    create = actions.add_parser(
        "create",
        help=f"create task/TASK from the default branch, and {task.NOTES_ROOT}/TASK/ on {task.NOTES_BRANCH} "
        "from config/task-template/",
        description="Uses git, with your own access to the project's repository. Refuses a task that already exists.",
    )
    _add_project_and_task(create)
    create.set_defaults(func=create_main)

    run = actions.add_parser(
        "run",
        help="start or re-attach to the sandbox for ROLE on TASK",
        description="Start the sandbox for ROLE on TASK in PROJECT, or re-attach to it if it already exists. "
        "A task with a task state starts only the role whose turn it is; `foundry task next` picks it for you.",
    )
    _add_project_and_task(run)
    run.add_argument("role_name", metavar="ROLE", help="role name, as listed in config/foundry.yaml")
    run.set_defaults(func=run_main)

    next_ = actions.add_parser(
        "next",
        help="run the role whose turn it is on TASK, or say what is waiting on you",
        description="Reads the task state from the project's notes branch, with git and your own access.",
    )
    _add_project_and_task(next_)
    next_.set_defaults(func=next_main)

    list_ = actions.add_parser(
        "list",
        help="every task's lifecycle, state, whose turn it is and hand-off note",
        description="Reads the notes branch of every project, or of PROJECT, with git and your own access.",
    )
    list_.add_argument("project_name", metavar="PROJECT", nargs="?", default=None, help=_PROJECT_HELP)
    list_.set_defaults(func=list_main)


def _add_project_and_task(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_name", metavar="PROJECT", help=_PROJECT_HELP)
    parser.add_argument("task_id", metavar="TASK", help=_TASK_HELP)


# --- create ------------------------------------------------------------------------


def create_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, task template and repository, in a scratch clone."""
    foundry_root = paths.find_foundry_root()
    project = config.load(foundry_root).project(args.project_name)
    new_task = task.Task(args.task_id)
    template = task.load_template(paths.task_template_dir(foundry_root))
    with tempfile.TemporaryDirectory(prefix="foundry-task-") as scratch_dir:
        task.create(GitClone.init(project.url, Path(scratch_dir), os.environ), new_task, template)
    print("\n".join(report(project.name, new_task)))
    return 0


def report(project_name: str, new_task: task.Task) -> list[str]:
    return [
        f"created task {new_task.id} in {project_name}",
        f"once its TASK.md is written, or to have the planner write it: foundry task next {project_name} {new_task.id}",
    ]


# --- run and next ------------------------------------------------------------------


def run_main(args: argparse.Namespace) -> NoReturn:
    """Composition root: prepare the launch from this foundry, then hand over to the sandbox."""
    _launch(paths.find_foundry_root(), project_name=args.project_name, role_name=args.role_name, task_id=args.task_id)


def next_main(args: argparse.Namespace) -> NoReturn:
    """Composition root: read the task state in a scratch clone, then launch its assignee as run does."""
    foundry_root = paths.find_foundry_root()
    project = config.load(foundry_root).project(args.project_name)
    the_task = Task(args.task_id)
    with tempfile.TemporaryDirectory(prefix="foundry-task-") as scratch_dir:
        clone = _notes_clone(project.url, Path(scratch_dir))
        state = task_state.read(clone, the_task)
    lifecycle = task_state.load_lifecycle(foundry_root, state.lifecycle) if state else None
    role_name = task_state.next_role(state, lifecycle, the_task, project_name=project.name)
    print(f"==> {the_task.id}: {role_name}'s turn", file=sys.stderr)
    _launch(foundry_root, project_name=project.name, role_name=role_name, task_id=the_task.id)


def _launch(foundry_root: Path, *, project_name: str, role_name: str, task_id: str) -> NoReturn:
    agent_sandbox.launch(
        prepare_launch(foundry_root, project_name=project_name, role_name=role_name, task=Task(task_id))
    )


def prepare_launch(foundry_root: Path, *, project_name: str, role_name: str, task: Task) -> agent_sandbox.LaunchRequest:
    """Everything up to the hand-over: the session, created the first time, and the request to launch it."""
    foundry_config = config.load(foundry_root)
    project = foundry_config.project(project_name)
    role = foundry_config.role(role_name)
    opened = session.open_or_create(foundry_root, project=project, role=role, task=task)
    if opened.created:
        print(f"==> session:   {opened.dir} (new)", file=sys.stderr)

    return agent_sandbox.LaunchRequest(
        definition_dir=opened.dir,
        ssh_key_path=role.ssh_key_path,
        init_command=opened.init_command,
        github_token_path=role.github_token_path,
    )


# --- list --------------------------------------------------------------------------


def list_main(args: argparse.Namespace) -> int:
    """Composition root: each project's notes branch in a scratch clone, and this foundry's lifecycles."""
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(foundry_root)
    projects = (
        [foundry_config.project(args.project_name)] if args.project_name else list(foundry_config.projects.values())
    )
    lifecycles: dict[str, Lifecycle] = {}

    def lifecycle(name: str) -> Lifecycle:
        if name not in lifecycles:
            lifecycles[name] = task_state.load_lifecycle(foundry_root, name)
        return lifecycles[name]

    for project in projects:
        with tempfile.TemporaryDirectory(prefix="foundry-task-") as scratch_dir:
            states = task_state.read_all(_notes_clone(project.url, Path(scratch_dir)))
        print("\n".join(list_lines(project.name, states, lifecycle)))
    return 0


def list_lines(
    project_name: str,
    states: Mapping[str, TaskState | FoundryError | None],
    lifecycle: Callable[[str], Lifecycle],
) -> list[str]:
    """The project, then a line per task: its lifecycle, state, whose turn, counts, and the note's first line."""
    lines = [project_name]
    for task_id, state in states.items():
        if state is None:
            lines.append(f"  {task_id}  no state")
            continue
        if isinstance(state, FoundryError):
            lines.append(f"  {task_id}  can't be read: {state}")
            continue
        try:
            assignee = lifecycle(state.lifecycle).assignee(state.state)
        except FoundryError as error:
            lines.append(f"  {task_id}  can't be read: {error}")
            continue
        turn = "done" if assignee is None else "your turn" if assignee == HUMAN else f"{assignee}'s turn"
        counts = [f"{key} {count}" for key, count in state.counts.items()]
        note = state.note.splitlines()[0] if state.note else ""
        lines.append(
            "  " + "  ".join(part for part in (task_id, state.lifecycle, state.state, turn, *counts, note) if part)
        )
    return lines if states else [project_name, "  no tasks"]


def _notes_clone(url: str, work_dir: Path) -> GitClone:
    clone = GitClone.init(url, work_dir, os.environ)
    clone.check_out(task.NOTES_BRANCH)
    return clone
