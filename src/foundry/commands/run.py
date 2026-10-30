"""foundry run: start or re-attach to the sandbox for a role on a task, by default the role whose turn it is."""

import argparse
import os
import sys
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session
from foundry.errors import FoundryError
from foundry.project_tasks import ProjectTasks
from foundry.runtime_build import build_runtime
from foundry.task import HUMAN, NOTES_BRANCH, Status, Task


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "run",
        help="start or re-attach to a sandboxed agent",
        description="Start the sandbox for ROLE on TASK in PROJECT, or re-attach to it if it already exists. "
        "Without ROLE, the role whose turn it is, as the task's TURN file on agent-notes says.",
    )
    parser.add_argument("project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
    parser.add_argument(
        "role_name", metavar="ROLE", nargs="?", help="role name, as listed in config/foundry.yaml; default: the turn's"
    )
    parser.add_argument("task_id", metavar="TASK", help="task id, e.g. wcf-0042")
    parser.set_defaults(func=main)


def main(args: argparse.Namespace) -> NoReturn:
    """Composition root: find the role, prepare the launch from this foundry, say what it created, then hand over."""
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(foundry_root)
    url = foundry_config.project(args.project_name).url
    with ProjectTasks.in_scratch_clone(url, os.environ) as project_tasks:
        task, role_name = require_open_task_and_role(
            project_tasks,
            project_name=args.project_name,
            task_id=args.task_id,
            role_name=args.role_name,
            roles=foundry_config.roles,
        )
    launch = prepare_launch(foundry_root, project_name=args.project_name, role_name=role_name, task=task)
    if launch.created:
        print(f"==> session:   {launch.request.definition_dir} (new)", file=sys.stderr)
    agent_sandbox.launch(launch.request)


def require_open_task_and_role(
    project_tasks: ProjectTasks, *, project_name: str, task_id: str, role_name: str | None, roles: Collection[str]
) -> tuple[Task, str]:
    """The open task, and the role to launch on it: ``role_name``, or the turn's when it is None.

    FoundryError, before any sandbox is made, when the task doesn't exist, or is closed (saying how to reopen it).
    """
    task = project_tasks.get_task_by_id(task_id)
    if task.status is Status.CLOSED:
        raise FoundryError(f"task {task.id} is closed: reopen it with `foundry task reopen {project_name} {task.id}`")
    if role_name is None:
        role_name = role_for_turn(project_tasks.read_task_turn(task.id), roles, project_name=project_name, task=task)
        print(f"==> turn:      {role_name}", file=sys.stderr)
    return task, role_name


def role_for_turn(turn: str, roles: Collection[str], *, project_name: str, task: Task) -> str:
    """The role to launch for ``turn``; FoundryError when the turn is HUMAN, since the task waits for you, or
    names no role in ``roles``."""
    override = f"To start a role anyway: foundry run {project_name} ROLE {task.id}"
    if turn == HUMAN:
        raise FoundryError(f"task {task.id} is waiting for you: see Blockers in its PROGRESS.md. {override}")
    if turn not in roles:
        known = ", ".join(sorted(roles)) or "none"
        raise FoundryError(
            f"task {task.id}'s {task.turn_file} on {NOTES_BRANCH} names {turn!r}, which is not a role; "
            f"known: {known}, or {HUMAN}. {override}"
        )
    return turn


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
