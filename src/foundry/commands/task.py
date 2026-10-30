"""foundry task create: a new task on a project, ready for foundry run."""

import argparse
import os
import tempfile
from pathlib import Path

from foundry import config, paths, task
from foundry.project_clone import ProjectClone
from foundry.project_tasks import ProjectTasks


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create, close and reopen tasks on projects")
    actions = parser.add_subparsers(dest="action", required=True)
    create = actions.add_parser(
        "create",
        help=f"create task/TASK from the default branch, and {task.OPEN_DIR}/TASK/ on {task.NOTES_BRANCH} "
        "from config/task-template/",
        description="Uses git, with your own access to the project's repository. "
        "Refuses a task that already exists, open or closed.",
    )
    create.add_argument("project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
    create.add_argument("task_id", metavar="TASK", help="task id, e.g. wcf-0042")
    create.set_defaults(func=create_main)
    close = actions.add_parser(
        "close",
        help=f"move {task.OPEN_DIR}/TASK/ to {task.CLOSED_DIR}/TASK/ on {task.NOTES_BRANCH}",
        description="Uses git, with your own access to the project's repository. Changes nothing else: not the "
        "task's branch, its sandboxes or its sessions. Refuses a task that is closed or doesn't exist.",
    )
    reopen = actions.add_parser(
        "reopen",
        help=f"move {task.CLOSED_DIR}/TASK/ back to {task.OPEN_DIR}/TASK/ on {task.NOTES_BRANCH}",
        description="Uses git, with your own access to the project's repository. Refuses a task that is open or "
        "doesn't exist.",
    )
    for parser_, main in ((close, close_main), (reopen, reopen_main)):
        parser_.add_argument("project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
        parser_.add_argument("task_id", metavar="TASK", help="task id, e.g. wcf-0042")
        parser_.set_defaults(func=main)


def create_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, task template and repository, in a scratch clone."""
    foundry_root = paths.find_foundry_root()
    project = config.load(foundry_root).project(args.project_name)
    new_task = task.Task.as_open(args.task_id)
    template = task.load_template(paths.task_template_dir(foundry_root))
    with tempfile.TemporaryDirectory(prefix="foundry-task-") as scratch_dir:
        ProjectTasks(ProjectClone.init(project.url, Path(scratch_dir), os.environ)).create(new_task, template)
    print("\n".join(report(project.name, new_task)))
    return 0


def close_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    closing = task.Task.as_open(args.task_id)
    with tempfile.TemporaryDirectory(prefix="foundry-task-") as scratch_dir:
        ProjectTasks(ProjectClone.init(project.url, Path(scratch_dir), os.environ)).close(closing)
    print(f"closed task {closing.id} in {project.name}")
    print(f"reopen it with: foundry task reopen {project.name} {closing.id}")
    return 0


def reopen_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    reopening = task.Task.as_closed(args.task_id)
    with tempfile.TemporaryDirectory(prefix="foundry-task-") as scratch_dir:
        ProjectTasks(ProjectClone.init(project.url, Path(scratch_dir), os.environ)).reopen(reopening)
    print(f"reopened task {reopening.id} in {project.name}")
    print(f"run it with: foundry run {project.name} {reopening.id}")
    return 0


def report(project_name: str, new_task: task.Task) -> list[str]:
    return [
        f"created task {new_task.id} in {project_name}",
        f"run it with: foundry run {project_name} {new_task.id}",
    ]
