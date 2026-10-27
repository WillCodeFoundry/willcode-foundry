"""foundry run: start or re-attach to the sandbox for a role on a task."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session
from foundry.errors import FoundryError
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
    """Composition root: prepare the launch from this foundry, then hand over to the sandbox."""
    task = Task(args.task_id)
    agent_sandbox.launch(
        prepare_launch(paths.find_foundry_root(), project_name=args.project_name, role_name=args.role_name, task=task)
    )


def prepare_launch(foundry_root: Path, *, project_name: str, role_name: str, task: Task) -> agent_sandbox.LaunchRequest:
    """Everything up to the hand-over: the session, created the first time, the agent runtime built into the
    kit its sandbox mounts, and the request to launch it.

    sbx fixes mounts when it creates a sandbox, so the kit the definition records must be this foundry's: a
    copied foundry would swap the runtime under the original's sandboxes, and a moved one's sandbox mounts a
    kit that is gone. Either is refused, saying what to do. A failed build aborts.
    """
    foundry_config = config.load(foundry_root)
    project = foundry_config.project(project_name)
    role = foundry_config.role(role_name)
    opened = session.open_or_create(foundry_root, project=project, role=role, task=task)
    if opened.created:
        print(f"==> session:   {opened.dir} (new)", file=sys.stderr)
    _require_own_kit(opened.definition.name, opened.definition.agent_kit_dir, paths.agent_kit_dir(foundry_root))
    build_runtime(opened.definition.agent_kit_dir)

    return agent_sandbox.LaunchRequest(
        definition_dir=opened.dir,
        ssh_key_path=role.ssh_key_path,
        init_command=opened.init_command,
        github_token_path=role.github_token_path,
    )


def _require_own_kit(sandbox_name: str, recorded: Path, own: Path) -> None:
    if recorded.resolve() == own.resolve():
        return
    see = "(see Recreating a sandbox in the README)"
    if recorded.is_dir():
        raise FoundryError(
            f"{sandbox_name} mounts the agent kit at {recorded}, not this foundry's ({own}): "
            f"launch it from the foundry there, or recreate it {see}"
        )
    raise FoundryError(f"{sandbox_name} mounts the agent kit at {recorded}, which is gone: recreate it {see}")
