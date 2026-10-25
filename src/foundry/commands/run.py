"""foundry run: start or re-attach to the sandbox for a role on a task."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session
from foundry.task import Task


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "run",
        help="start or re-attach to a sandboxed agent",
        description="Start the sandbox for ROLE on TASK in PROJECT, or re-attach to it if it already exists.",
    )
    parser.add_argument("project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
    parser.add_argument("role_name", metavar="ROLE", help="role name, as listed in config/foundry.yaml")
    parser.add_argument("task_id", metavar="TASK", help="task id, e.g. wcf-0042")
    parser.set_defaults(func=main)


def main(args: argparse.Namespace) -> NoReturn:
    """Composition root: prepare the launch from this foundry, then hand over to the sandbox."""
    task = Task(args.task_id)
    agent_sandbox.launch(
        prepare_launch(paths.find_foundry_root(), project_name=args.project_name, role_name=args.role_name, task=task)
    )


def prepare_launch(foundry_root: Path, *, project_name: str, role_name: str, task: Task) -> agent_sandbox.LaunchRequest:
    """Everything up to the hand-over: the session, created the first time, and the request to launch it."""
    foundry_config = config.load(paths.config_path(foundry_root))
    project = foundry_config.project(project_name)
    role = foundry_config.role(role_name)
    opened = session.open_or_create(foundry_root, project=project, role=role, task=task)
    if opened.created:
        print(f"==> session:   {opened.dir} (new)", file=sys.stderr)

    github_token_path = paths.github_token_path(foundry_root, role.name)
    return agent_sandbox.LaunchRequest(
        definition_dir=opened.dir,
        ssh_key_path=paths.ssh_key_path(foundry_root, role.name),
        init_command=opened.init_command,
        github_token_path=github_token_path if github_token_path.is_file() else None,
    )
