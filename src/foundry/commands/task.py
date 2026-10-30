"""foundry task: create a task on a project, ready for foundry run, and close and reopen it."""

import argparse
import os
from typing import NamedTuple

from foundry import config, paths, task
from foundry.project_tasks import ProjectTasks


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create, close and reopen tasks on projects")
    actions = parser.add_subparsers(dest="action", required=True)
    # The arguments every action takes.
    task_arguments = argparse.ArgumentParser(add_help=False)
    task_arguments.add_argument(
        "project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml"
    )
    task_arguments.add_argument("task_id", metavar="TASK", help="task id, e.g. wcf-0042")
    create = actions.add_parser(
        "create",
        parents=[task_arguments],
        help=f"create task/TASK from the default branch, and {task.OPEN_DIR}/TASK/ on {task.NOTES_BRANCH} "
        "from config/task-template/",
        description="Uses git, with your own access to the project's repository. "
        "Refuses a task that already exists, open or closed.",
    )
    create.set_defaults(func=create_main)
    close = actions.add_parser(
        "close",
        parents=[task_arguments],
        help=f"move {task.OPEN_DIR}/TASK/ to {task.CLOSED_DIR}/TASK/ on {task.NOTES_BRANCH}",
        description="Uses git, with your own access to the project's repository. Changes nothing else: not the "
        "task's branch, its sandboxes or its sessions. Refuses a task that is closed or doesn't exist.",
    )
    close.set_defaults(func=close_main)
    reopen = actions.add_parser(
        "reopen",
        parents=[task_arguments],
        help=f"move {task.CLOSED_DIR}/TASK/ back to {task.OPEN_DIR}/TASK/ on {task.NOTES_BRANCH}",
        description="Uses git, with your own access to the project's repository. Refuses a task that is open or "
        "doesn't exist.",
    )
    reopen.set_defaults(func=reopen_main)


def create_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, task template and repository, in a scratch clone."""
    foundry_root = paths.find_foundry_root()
    project = config.load(foundry_root).project(args.project_name)
    template = task.load_template(paths.task_template_dir(foundry_root))
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as tasks:
        created = tasks.create_task(args.task_id, template)
    print("\n".join(report(CREATED, project.name, created)))
    return 0


def close_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as tasks:
        closed = tasks.close_task(args.task_id)
    print("\n".join(report(CLOSED, project.name, closed)))
    return 0


def reopen_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as tasks:
        reopened = tasks.reopen_task(args.task_id)
    print("\n".join(report(REOPENED, project.name, reopened)))
    return 0


class Outcome(NamedTuple):
    """What an action did to the task, and what you do next."""

    done: str
    next_command: str


CREATED = Outcome("created", "run it with: foundry run")
CLOSED = Outcome("closed", "reopen it with: foundry task reopen")
REOPENED = Outcome("reopened", "run it with: foundry run")


def report(outcome: Outcome, project_name: str, changed: task.Task) -> list[str]:
    return [
        f"{outcome.done} task {changed.id} in {project_name}",
        f"{outcome.next_command} {project_name} {changed.id}",
    ]
