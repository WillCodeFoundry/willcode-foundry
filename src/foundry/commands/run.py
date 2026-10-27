"""foundry run: start or re-attach to the sandbox for a role on a task."""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session
from foundry.runtime_build import build_runtime
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
    """Composition root: prepare the launch from this foundry, say what it created, then hand over."""
    launch = prepare_launch(
        paths.find_foundry_root(), project_name=args.project_name, role_name=args.role_name, task=Task(args.task_id)
    )
    if launch.created:
        print(f"==> session:   {launch.request.definition_dir} (new)", file=sys.stderr)
    agent_sandbox.launch(launch.request)


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
