"""foundry run: start or re-attach to the sandbox for a role on a task."""

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "run",
        help="start or re-attach to a sandboxed agent",
        usage="foundry run PROJECT ROLE TASK [-- AGENT_ARGS...]",
        description=(
            "Start the sandbox for ROLE on TASK in PROJECT, or re-attach to it if it already exists. "
            "Arguments after '--' go to the agent."
        ),
    )
    parser.add_argument("project", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
    parser.add_argument("role", metavar="ROLE", help="role name, as listed in config/foundry.yaml")
    parser.add_argument("task_id", metavar="TASK", help="task id, e.g. WCF-0042")
    parser.set_defaults(func=main)


def main(args: argparse.Namespace, agent_args: tuple[str, ...]) -> NoReturn:
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(paths.config_path(foundry_root))
    project = foundry_config.project(args.project)
    role = foundry_config.role(args.role)
    session.require_valid_task_id(args.task_id)
    sandbox_name = session.sandbox_name(role.name, project.name, args.task_id)
    session_dir = paths.session_dir(foundry_root, sandbox_name)
    launched_at = datetime.now().astimezone()

    if not (session_dir / agent_sandbox.definition.DEFINITION_FILE_NAME).is_file():
        _create_session(session_dir, foundry_root, sandbox_name, project, role, args.task_id, launched_at)
    sandbox = agent_sandbox.definition.read(session_dir)
    session.require_same_sandbox(sandbox, role_name=role.name, task_id=args.task_id, repo_url=project.url)

    # The workspace is an empty temporary directory; recreate it if the OS has
    # cleared it since the sandbox was created (after a reboot, say).
    sandbox.workspace_dir.mkdir(parents=True, exist_ok=True)
    session.record_launch(session_dir, launched_at=launched_at)

    github_token_path = paths.github_token_path(foundry_root, role.name)
    agent_sandbox.launch(
        agent_sandbox.LaunchRequest(
            definition_dir=session_dir,
            ssh_key_path=paths.ssh_key_path(foundry_root, role.name),
            init_command=(str(sandbox.agent_kit_dir / "bin" / "session-init"),),
            github_token_path=github_token_path if github_token_path.is_file() else None,
            agent_args=agent_args,
        )
    )


def _create_session(
    session_dir: Path,
    foundry_root: Path,
    sandbox_name: str,
    project: config.Project,
    role: config.Role,
    task_id: str,
    created_at: datetime,
) -> None:
    sandbox = session.sandbox_definition(
        sandbox_name=sandbox_name,
        workspace_dir=Path(tempfile.mkdtemp(prefix=f"foundry-{sandbox_name}-")),
        agent_kit_dir=paths.agent_kit_dir(foundry_root),
        repo_url=project.url,
        role_name=role.name,
        task_id=task_id,
        project_name=project.name,
    )
    session.create_session(
        session_dir,
        sandbox,
        sandbox=sandbox_name,
        role=role.name,
        project=project.name,
        task=task_id,
        branch=f"task/{task_id}",
        created=created_at.isoformat(timespec="seconds"),
    )
    print(f"==> session:   {session_dir} (new)", file=sys.stderr)
