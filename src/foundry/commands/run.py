"""foundry run: start or re-attach to the sandbox for a role on a task, by default the role whose turn it is."""

import argparse
import os
import sys
from collections.abc import Collection
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths
from foundry.config import Config, Project, Role
from foundry.errors import FoundryError
from foundry.project_tasks import ProjectTasks
from foundry.runtime_build import build_runtime
from foundry.session import open_or_create
from foundry.task import HUMAN, LOG_FILE, NOTES_BRANCH, Status, Task


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
    """Composition root: find the open task and the role, make the launch request, then launch."""
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(foundry_root)
    project = foundry_config.project(args.project_name)
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as project_tasks:
        task = fetch_open_task(project_tasks, project_name=project.name, task_id=args.task_id)
        role = choose_role(
            project_tasks, foundry_config, project_name=project.name, task=task, role_name=args.role_name
        )
    agent_sandbox.launch(make_launch_request(foundry_root, project=project, role=role, task=task))


def fetch_open_task(project_tasks: ProjectTasks, *, project_name: str, task_id: str) -> Task:
    """The open task named ``task_id``. FoundryError, before any sandbox is made, when it doesn't exist or is closed,
    saying how to reopen it."""
    task = project_tasks.fetch_task(task_id)
    if task.status is Status.CLOSED:
        raise FoundryError(f"task {task.id} is closed: reopen it with `foundry task reopen {project_name} {task.id}`")
    return task


def choose_role(
    project_tasks: ProjectTasks, foundry_config: Config, *, project_name: str, task: Task, role_name: str | None
) -> Role:
    """The role to launch on ``task``: ``role_name``, or the turn's when it is None, read from NOTES_BRANCH and
    printed. FoundryError, before any sandbox is made, when the role isn't in the config or the turn names none."""
    if role_name is None:
        turn = project_tasks.fetch_task_turn(task.id)
        role_name = role_for_turn(turn, foundry_config.roles, project_name=project_name, task=task)
        print(f"==> turn:      {role_name}", file=sys.stderr)
    return foundry_config.role(role_name)


def role_for_turn(turn: str, roles: Collection[str], *, project_name: str, task: Task) -> str:
    """The role to launch for ``turn``; FoundryError when the turn is HUMAN, since the task waits for you, or
    names no role in ``roles``."""
    override_hint = f"To start a role anyway: foundry run {project_name} ROLE {task.id}"
    if turn == HUMAN:
        raise FoundryError(f"task {task.id} is waiting for you: see the last entry in its {LOG_FILE}. {override_hint}")
    if turn not in roles:
        known = ", ".join(sorted(roles)) or "none"
        raise FoundryError(
            f"task {task.id}'s {task.turn_file} on {NOTES_BRANCH} names {turn!r}, which is not a role; "
            f"known: {known}, or {HUMAN}. {override_hint}"
        )
    return turn


def make_launch_request(foundry_root: Path, *, project: Project, role: Role, task: Task) -> agent_sandbox.LaunchRequest:
    """What agent_sandbox needs to launch ``role`` on ``task``: the session, created and printed the first time, and
    the agent runtime built into the kit. A failed build aborts."""
    session = open_or_create(foundry_root, project=project, role=role, task=task)
    if session.created:
        print(f"==> session:   {session.dir} (new)", file=sys.stderr)
    build_runtime(paths.agent_kit_dir(foundry_root))
    return agent_sandbox.LaunchRequest(
        definition_dir=session.dir,
        ssh_key_path=role.ssh_key_path,
        init_command=session.init_command,
        github_token_path=role.github_token_path,
        model=role.model,
    )
