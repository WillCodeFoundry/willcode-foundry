"""foundry run: start or re-attach to the sandbox for a role on a task."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "run",
        help="start or re-attach to a sandboxed agent",
        description="Start the sandbox for ROLE on TASK in PROJECT, or re-attach to it if it already exists.",
    )
    parser.add_argument("project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
    parser.add_argument("role_name", metavar="ROLE", help="role name, as listed in config/foundry.yaml")
    parser.add_argument("task_id", metavar="TASK", help="task id, e.g. WCF-0042")
    parser.set_defaults(func=main)


def main(args: argparse.Namespace) -> NoReturn:
    """Composition root: prepare the launch from this foundry, then hand over to the sandbox."""
    agent_sandbox.launch(prepare_launch(paths.find_foundry_root(), args.project_name, args.role_name, args.task_id))


def prepare_launch(foundry_root: Path, project_name: str, role_name: str, task_id: str) -> agent_sandbox.LaunchRequest:
    """Everything up to the hand-over: the session, created the first time, and the request to launch it."""
    foundry_config = config.load(paths.config_path(foundry_root))
    project = foundry_config.project(project_name)
    role = foundry_config.role(role_name)
    session.require_valid_task_id(task_id)
    sandbox_name = session.sandbox_name(role.name, project.name, task_id)
    session_dir = paths.session_dir(foundry_root, sandbox_name)

    if not (session_dir / agent_sandbox.SandboxDefinition.FILE_NAME).is_file():
        new_definition = session.sandbox_definition(
            sandbox_name=sandbox_name,
            workspace_dir=paths.workspace_dir(foundry_root, sandbox_name),
            agent_kit_dir=paths.agent_kit_dir(foundry_root),
            repo_url=project.url,
            role_name=role.name,
            task_id=task_id,
            project_name=project.name,
        )
        session.create(session_dir, new_definition)
        print(f"==> session:   {session_dir} (new)", file=sys.stderr)
    definition = agent_sandbox.SandboxDefinition.read(session_dir)
    session.require_same_sandbox(definition, role_name=role.name, task_id=task_id, repo_url=project.url)

    github_token_path = paths.github_token_path(foundry_root, role.name)
    return agent_sandbox.LaunchRequest(
        definition_dir=session_dir,
        ssh_key_path=paths.ssh_key_path(foundry_root, role.name),
        init_command=(str(definition.agent_kit_dir / "bin" / "session-init"),),
        github_token_path=github_token_path if github_token_path.is_file() else None,
    )
