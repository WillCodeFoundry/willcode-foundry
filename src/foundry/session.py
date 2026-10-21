"""Sessions: one directory per sandbox, holding its environment file and record.

``sessions/<sandbox>/sbxenv.yaml`` is written once, when the sandbox is first
run, and describes the sandbox for its whole life: sbx fixes a sandbox's mounts
when it is created. ``session.yaml`` records when it was created and each
launch since.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Final, TypedDict, cast

from foundry import yaml_io
from foundry.errors import FoundryError

ENV_FILE: Final = "sbxenv.yaml"
RECORD_FILE: Final = "session.yaml"

# The environment variables every sandbox gets; AGENTS.md, the kit's scripts
# and the hooks read them by these names.
ROLE: Final = "AGENT_ROLE"
TASK: Final = "AGENT_TASK"
KIT_DIR: Final = "AGENT_KIT_DIR"
REPO_URL: Final = "AGENT_REPO_URL"
PROJECT_DIR: Final = "AGENT_PROJECT_DIR"
NOTES_DIR: Final = "AGENT_NOTES_DIR"

# sbx accepts letters, digits, '.', '+', '-', starting with a letter or digit.
# The name also names an ssh-agent socket, whose path length is limited.
MAX_SANDBOX_NAME: Final = 64
_UNSAFE = re.compile(r"[^A-Za-z0-9.+-]+")

# Inside the sandbox: where session-init clones the project. Nothing on the
# host corresponds to these paths; they assume the template's `agent` user.
WORK_DIR: Final = "/home/agent/work"


class Mount(TypedDict):
    path: str
    readOnly: bool


class EnvFile(TypedDict):
    """The parts of sbxenv.yaml the foundry writes and reads back."""

    schemaVersion: str
    name: str
    agent: str
    workspace: str
    additionalWorkspaces: list[Mount]
    env: dict[str, str]


def _slug(text: str) -> str:
    return _UNSAFE.sub("-", text).strip("-").lower()


def sandbox_name(role: str, project: str, task: str) -> str:
    """Stable per (role, project, task), so a rerun re-attaches: dev-tkt-store-wcf-0042."""
    name = "-".join(_slug(part) for part in (role, project, task))
    if not name or not name[0].isalnum():
        raise FoundryError(f"cannot build a valid sandbox name from role={role!r} project={project!r} task={task!r}")
    if len(name) > MAX_SANDBOX_NAME:
        raise FoundryError(
            f"sandbox name {name!r} is over {MAX_SANDBOX_NAME} characters; shorten the project or task name"
        )
    return name


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
    task: str,
    project: str,
    agent: str = "claude",
) -> EnvFile:
    """The sbxenv.yaml structure.

    ``workspace`` is an empty temporary directory: sbx requires a primary
    workspace before it accepts additional ones, but nothing goes in it. The
    kit is mounted read-only; the project is cloned inside the sandbox by
    session-init.
    """
    return {
        "schemaVersion": "1",
        "name": sandbox,
        "agent": agent,
        "workspace": str(workspace),
        "additionalWorkspaces": [{"path": str(kit_dir), "readOnly": True}],
        "env": {
            ROLE: role,
            TASK: task,
            KIT_DIR: str(kit_dir),
            REPO_URL: repo_url,
            PROJECT_DIR: project_dir(project),
            NOTES_DIR: notes_dir(project),
        },
    }


def workspace_dir(document: EnvFile) -> Path:
    return Path(document["workspace"])


def kit_dir(document: EnvFile) -> Path:
    return Path(document["additionalWorkspaces"][0]["path"])


def create_session(session_dir: Path, document: EnvFile, **record: Any) -> None:
    """Create the session directory with its sbxenv.yaml and session.yaml.

    Refuses if the directory already exists, so an existing sandbox's
    environment file is never rewritten.
    """
    try:
        session_dir.mkdir(parents=True)
    except FileExistsError:
        raise FoundryError(f"session directory {session_dir} already exists") from None
    yaml_io.dump(session_dir / ENV_FILE, document)
    yaml_io.dump(session_dir / RECORD_FILE, {**record, "launches": []})


def read_env_file(session_dir: Path) -> EnvFile:
    path = session_dir / ENV_FILE
    doc = yaml_io.load(path)
    try:
        if not all(isinstance(doc[key], str) for key in ("name", "workspace")):
            raise TypeError
        _ = doc["env"][ROLE], doc["env"][TASK], doc["additionalWorkspaces"][0]["path"]
    except (TypeError, KeyError, IndexError):
        raise FoundryError(f"{path} is not a foundry sandbox environment file") from None
    return cast(EnvFile, doc)


def read_record(session_dir: Path) -> dict[str, Any]:
    path = session_dir / RECORD_FILE
    record = yaml_io.load(path)
    if not isinstance(record, dict):
        raise FoundryError(f"{path} is not a session record")
    return record


def record_launch(session_dir: Path, *, at: datetime, fresh: bool) -> None:
    """Append one launch to session.yaml, keeping everything already there."""
    record = read_record(session_dir)
    launches = record.get("launches") or []
    record["launches"] = [*launches, {"at": at.isoformat(timespec="seconds"), "fresh": fresh}]
    yaml_io.dump(session_dir / RECORD_FILE, record)
