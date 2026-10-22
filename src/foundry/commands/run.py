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
        usage="foundry run PROJECT ROLE TASK [--fresh] [-- AGENT_ARGS...]",
        description=(
            "Start the sandbox for ROLE on TASK in PROJECT, or re-attach to it if it already exists. "
            "Arguments after '--' go to the agent."
        ),
    )
    parser.add_argument("project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
    parser.add_argument("role_name", metavar="ROLE", help="role name, as listed in config/foundry.yaml")
    parser.add_argument("task_id", metavar="TASK", help="task id, e.g. WCF-0042")
    parser.add_argument("--fresh", action="store_true", help="remove the existing sandbox first and start a new one")
    parser.set_defaults(func=main)


def main(args: argparse.Namespace, agent_args: tuple[str, ...]) -> NoReturn:
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(paths.config_path(foundry_root))
    project = foundry_config.project(args.project_name)
    role = foundry_config.role(args.role_name)
    session.ensure_valid_task_id(args.task_id)
    sandbox_name = session.sandbox_name(role.role_name, project.project_name, args.task_id)
    session_path = paths.session_path(foundry_root, sandbox_name)
    launched_at = datetime.now().astimezone()

    if not (session_path / session.ENV_FILE_NAME).is_file():
        _create_session(session_path, foundry_root, sandbox_name, project, role, args.task_id, launched_at)
    env_file = session.read_env_file(session_path)
    session.ensure_env_file_matches(env_file, role_name=role.role_name, task_id=args.task_id, repo_url=project.url)

    # The workspace is an empty temporary directory; recreate it if the OS has
    # cleared it since the sandbox was created (after a reboot, say).
    session.workspace_path(env_file).mkdir(parents=True, exist_ok=True)
    session.record_launch(session_path, launched_at=launched_at, fresh=args.fresh)

    github_token_path = paths.github_token_path(foundry_root, role.role_name)
    agent_kit_path = session.agent_kit_path(env_file)
    agent_sandbox.run_sandbox(
        agent_sandbox.Launch(
            sandbox_name=env_file["name"],
            env_dir_path=session_path,
            agent_kit_path=agent_kit_path,
            ssh_key_path=paths.ssh_key_path(foundry_root, role.role_name),
            init_command=(str(agent_kit_path / "bin" / "session-init"),),
            github_token_path=github_token_path if github_token_path.is_file() else None,
            agent_args=agent_args,
            fresh=args.fresh,
        )
    )


def _create_session(
    session_path: Path,
    foundry_root: Path,
    sandbox_name: str,
    project: config.Project,
    role: config.Role,
    task_id: str,
    created_at: datetime,
) -> None:
    env_file = session.build_env_file(
        sandbox_name=sandbox_name,
        workspace_path=Path(tempfile.mkdtemp(prefix=f"foundry-{sandbox_name}-")),
        agent_kit_path=paths.agent_kit_path(foundry_root),
        repo_url=project.url,
        role_name=role.role_name,
        task_id=task_id,
        project_name=project.project_name,
    )
    session.create_session(
        session_path,
        env_file,
        sandbox=sandbox_name,
        role=role.role_name,
        project=project.project_name,
        task=task_id,
        branch=f"task/{task_id}",
        created=created_at.isoformat(timespec="seconds"),
    )
    print(f"==> session:   {session_path} (new)", file=sys.stderr)
