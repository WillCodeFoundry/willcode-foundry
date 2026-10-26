"""foundry task: everything done to one task, each subcommand taking PROJECT TASK first.

create makes the task; run launches a role on it.
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session, task
from foundry.git_clone import GitClone
from foundry.task import Task

_PROJECT_HELP = "project name, as listed in config/foundry.yaml"
_TASK_HELP = "task id, e.g. wcf-0042"


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create and run tasks")
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
        "A task with a task state starts only the role whose turn it is.",
    )
    _add_project_and_task(run)
    run.add_argument("role_name", metavar="ROLE", help="role name, as listed in config/foundry.yaml")
    run.set_defaults(func=run_main)


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
        f"run it with: foundry task run {project_name} {new_task.id} ROLE",
    ]


# --- run ---------------------------------------------------------------------------


def run_main(args: argparse.Namespace) -> NoReturn:
    """Composition root: prepare the launch from this foundry, then hand over to the sandbox."""
    agent_sandbox.launch(
        prepare_launch(
            paths.find_foundry_root(), project_name=args.project_name, role_name=args.role_name, task=Task(args.task_id)
        )
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
