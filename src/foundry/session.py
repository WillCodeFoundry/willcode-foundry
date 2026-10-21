"""Sessions: naming, the sandbox environment file, and the session record.

A session directory holds sbxenv.yaml, written once when the session is
created, and session.yaml, written then and updated afterwards.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from foundry import yaml_io
from foundry.errors import FoundryError

ENV_FILE = "sbxenv.yaml"
RECORD_FILE = "session.yaml"

# sbx accepts letters, digits, '.', '+', '-', starting with a letter or digit.
# The name also names an ssh-agent socket, whose path length is limited.
MAX_SANDBOX_NAME = 64
_UNSAFE = re.compile(r"[^A-Za-z0-9.+-]+")

# Inside the sandbox: where session-init clones the project. Nothing on the
# host corresponds to these paths.
WORK_DIR = "/home/agent/work"


def _slug(text: str) -> str:
    return _UNSAFE.sub("-", text).strip("-").lower()


def sandbox_name(role: str, project: str, task: str | None) -> str:
    """Stable per (role, project, task), so a rerun re-attaches: dev-tkt-store-wcf-0042."""
    name = "-".join(_slug(part) for part in (role, project, task) if part)
    if not name or not name[0].isalnum():
        raise FoundryError(f"cannot build a valid sandbox name from role={role!r} project={project!r} task={task!r}")
    if len(name) > MAX_SANDBOX_NAME:
        raise FoundryError(f"sandbox name {name!r} is over {MAX_SANDBOX_NAME} characters; shorten the project or task name")
    return name


def session_name(now: datetime, sandbox: str) -> str:
    """One per run, chronological in a listing: 20261021-163005-dev-tkt-store-wcf-0042."""
    return f"{now:%Y%m%d-%H%M%S}-{sandbox}"


def project_dir(project: str) -> str:
    return f"{WORK_DIR}/{_slug(project)}"


def notes_dir(project: str) -> str:
    return f"{project_dir(project)}-notes"


def env_document(
    *,
    sandbox: str,
    workspace: Path,
    kit_dir: Path,
    repo_url: str,
    role: str,
    task: str | None,
    project: str,
    agent: str = "claude",
) -> dict[str, Any]:
    """The sbxenv.yaml structure.

    ``workspace`` is an empty temporary directory: sbx requires a primary
    workspace before it accepts additional ones, but nothing goes in it. The
    kit is mounted read-only; the project is cloned inside the sandbox by
    session-init.
    """
    env = {
        "AGENT_ROLE": role,
        "AGENT_KIT_DIR": str(kit_dir),
        "AGENT_REPO_URL": repo_url,
        "AGENT_PROJECT_DIR": project_dir(project),
        "AGENT_NOTES_DIR": notes_dir(project),
    }
    if task:
        env["AGENT_TASK"] = task
    return {
        "schemaVersion": "1",
        "name": sandbox,
        "agent": agent,
        "workspace": str(workspace),
        "additionalWorkspaces": [{"path": str(kit_dir), "readOnly": True}],
        "env": env,
    }


def workspace_dir(document: dict[str, Any]) -> Path:
    return Path(document["workspace"])


def kit_dir(document: dict[str, Any]) -> Path:
    return Path(document["additionalWorkspaces"][0]["path"])


def create_session(session_dir: Path, document: dict[str, Any], **record: Any) -> None:
    """Create the session directory with its sbxenv.yaml and session.yaml.

    Refuses if the directory already exists: a sandbox's mounts are fixed when
    it is created, so an existing session's file must never be rewritten.
    """
    try:
        session_dir.mkdir(parents=True)
    except FileExistsError:
        raise FoundryError(f"session directory {session_dir} already exists") from None
    yaml_io.dump(session_dir / ENV_FILE, document)
    yaml_io.dump(session_dir / RECORD_FILE, record)


def read_env_file(session_dir: Path) -> dict[str, Any]:
    path = session_dir / ENV_FILE
    doc = yaml_io.load(path)
    try:
        doc["name"], doc["env"]["AGENT_ROLE"], workspace_dir(doc), kit_dir(doc)
    except (TypeError, KeyError, IndexError):
        raise FoundryError(f"{path} is not a foundry sandbox environment file") from None
    return doc  # type: ignore[no-any-return]


def read_record(session_dir: Path) -> dict[str, Any]:
    record = yaml_io.load(session_dir / RECORD_FILE)
    if not isinstance(record, dict):
        raise FoundryError(f"{session_dir / RECORD_FILE} is not a session record")
    return record


def update_record(session_dir: Path, **fields: Any) -> None:
    """Merge fields into session.yaml, keeping everything already there."""
    record = read_record(session_dir)
    record.update(fields)
    yaml_io.dump(session_dir / RECORD_FILE, record)
