"""foundry run: start a role on a project, or re-run an existing session."""

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from foundry import agent_sandbox, config, paths, session
from foundry.errors import FoundryError


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser(
        "run",
        help="start a sandboxed agent",
        usage="foundry run (PROJECT ROLE [TASK] | SESSION_DIR) [--new] [-- AGENT_ARGS...]",
        description=(
            "Start a role on a project, writing a new session under sessions/, or re-run an "
            "existing session directory. Arguments after '--' go to the agent."
        ),
    )
    p.add_argument("target", help="project name (from config) or an existing session directory")
    p.add_argument("role", nargs="?", help="role name (from config); omitted when target is a session directory")
    p.add_argument("task", nargs="?", help="task id, e.g. WCF-0042")
    p.add_argument("--new", action="store_true", help="remove an existing sandbox of this name and start fresh")
    p.set_defaults(func=main)


def main(args: argparse.Namespace, agent_args: tuple[str, ...]) -> NoReturn:
    target = Path(args.target)
    if (target / session.ENV_FILE).is_file():
        root, session_dir, doc = _existing_session(target, args)
    else:
        root, session_dir, doc = _new_session(args)

    role = doc["env"]["AGENT_ROLE"]
    kit = session.kit_dir(doc)
    # The workspace is an empty temporary directory; recreate it if the OS has
    # cleared it since the session was created (e.g. after a reboot).
    session.workspace_dir(doc).mkdir(parents=True, exist_ok=True)
    token_file = paths.github_token(root, role)

    agent_sandbox.run(
        agent_sandbox.Launch(
            name=doc["name"],
            env_dir=session_dir,
            context=kit,
            ssh_key=paths.ssh_key(root, role),
            init=(str(kit / "bin" / "session-init"),),
            github_token=token_file.read_text().strip() if token_file.is_file() else None,
            agent_args=agent_args,
            fresh=args.new,
        )
    )


def _existing_session(target: Path, args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    if args.role or args.task:
        raise FoundryError("a session directory takes no role or task; they are in its sbxenv.yaml")
    session_dir = target.resolve()
    return paths.find_root(session_dir), session_dir, session.read_env_file(session_dir)


def _new_session(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    if not args.role:
        raise FoundryError("usage: foundry run PROJECT ROLE [TASK]  or  foundry run SESSION_DIR")
    root = paths.find_root()
    cfg = config.load(paths.config_file(root))
    project = cfg.project(args.target)
    role = cfg.role(args.role).name
    name = session.sandbox_name(role, project.name, args.task)
    now = datetime.now().astimezone()
    session_dir = paths.session_dir(root, session.session_name(now, name))
    doc = session.env_document(
        sandbox=name,
        workspace=Path(tempfile.mkdtemp(prefix=f"foundry-{name}-")),
        kit_dir=paths.kit(root),
        repo_url=project.url,
        role=role,
        task=args.task,
        project=project.name,
    )
    session.create_session(
        session_dir,
        doc,
        sandbox=name,
        role=role,
        project=project.name,
        task=args.task,
        branch=f"task/{args.task}" if args.task else None,
        created=now.isoformat(timespec="seconds"),
        status="created",
    )
    print(f"==> session:   {session_dir}", file=sys.stderr)
    return root, session_dir, doc
