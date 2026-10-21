"""foundry run: start or re-attach to the sandbox for a role on a task."""

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from foundry import agent_sandbox, config, paths, session


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser(
        "run",
        help="start or re-attach to a sandboxed agent",
        usage="foundry run PROJECT ROLE TASK [--new] [-- AGENT_ARGS...]",
        description=(
            "Start the sandbox for ROLE on TASK in PROJECT, or re-attach to it if it already exists. "
            "Arguments after '--' go to the agent."
        ),
    )
    p.add_argument("project", help="project name, as listed in config/foundry.yaml")
    p.add_argument("role", help="role name, as listed in config/foundry.yaml")
    p.add_argument("task", help="task id, e.g. WCF-0042")
    p.add_argument("--new", action="store_true", help="remove the existing sandbox first and start a fresh one")
    p.set_defaults(func=main)


def main(args: argparse.Namespace, agent_args: tuple[str, ...]) -> NoReturn:
    root = paths.find_root()
    cfg = config.load(paths.config_file(root))
    project = cfg.project(args.project)
    role = cfg.role(args.role).name
    name = session.sandbox_name(role, project.name, args.task)
    session_dir = paths.session_dir(root, name)
    now = datetime.now().astimezone()

    if not (session_dir / session.ENV_FILE).is_file():
        _create(session_dir, root, name, project, role, args.task, now)
    doc = session.read_env_file(session_dir)

    # The workspace is an empty temporary directory; recreate it if the OS has
    # cleared it since the sandbox was created (after a reboot, say).
    session.workspace_dir(doc).mkdir(parents=True, exist_ok=True)
    session.record_launch(session_dir, at=now, fresh=args.new)

    token_file = paths.github_token_file(root, role)
    kit = session.kit_dir(doc)
    agent_sandbox.run(
        agent_sandbox.Launch(
            name=doc["name"],
            env_dir=session_dir,
            context=kit,
            ssh_key=paths.ssh_key(root, role),
            init=(str(kit / "bin" / "session-init"),),
            github_token_file=token_file if token_file.is_file() else None,
            agent_args=agent_args,
            fresh=args.new,
        )
    )


def _create(
    session_dir: Path,
    root: Path,
    name: str,
    project: config.Project,
    role: str,
    task: str,
    now: datetime,
) -> None:
    doc = session.env_document(
        sandbox=name,
        workspace=Path(tempfile.mkdtemp(prefix=f"foundry-{name}-")),
        kit_dir=paths.kit(root),
        repo_url=project.url,
        role=role,
        task=task,
        project=project.name,
    )
    session.create_session(
        session_dir,
        doc,
        sandbox=name,
        role=role,
        project=project.name,
        task=task,
        branch=f"task/{task}",
        created=now.isoformat(timespec="seconds"),
    )
    print(f"==> session:   {session_dir} (new)", file=sys.stderr)
