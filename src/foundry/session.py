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

ENV_FILE_NAME: Final = "sbxenv.yaml"
RECORD_FILE_NAME: Final = "session.yaml"

# The environment variables every sandbox gets; AGENTS.md, the kit's scripts
# and the hooks read them by these names.
AGENT_ROLE_VAR: Final = "AGENT_ROLE"
AGENT_TASK_VAR: Final = "AGENT_TASK"
AGENT_KIT_DIR_VAR: Final = "AGENT_KIT_DIR"
AGENT_REPO_URL_VAR: Final = "AGENT_REPO_URL"
AGENT_PROJECT_DIR_VAR: Final = "AGENT_PROJECT_DIR"
AGENT_NOTES_DIR_VAR: Final = "AGENT_NOTES_DIR"

# sbx accepts letters, digits, '.', '+', '-', starting with a letter or digit.
# The name also names an ssh-agent socket, whose path length is limited.
MAX_SANDBOX_NAME_LENGTH: Final = 64
_SBX_UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9.+-]+")

# Inside the sandbox: where session-init clones the project. Nothing on the
# host corresponds to this path; it assumes the template's `agent` user.
SANDBOX_WORK_PATH: Final = "/home/agent/work"


class Mount(TypedDict):
    path: str
    readOnly: bool


class EnvFile(TypedDict):
    """The parts of sbxenv.yaml the foundry writes and reads back. Keys follow sbx's schema."""

    schemaVersion: str
    name: str
    agent: str
    workspace: str
    additionalWorkspaces: list[Mount]
    env: dict[str, str]


def _slug(text: str) -> str:
    return _SBX_UNSAFE_CHARACTERS.sub("-", text).strip("-").lower()


def sandbox_name(role_name: str, project_name: str, task_id: str) -> str:
    """Stable per (role, project, task), so a rerun re-attaches: dev-tkt-store-wcf-0042."""
    name = "-".join(_slug(part) for part in (role_name, project_name, task_id))
    if not name or not name[0].isalnum():
        raise FoundryError(
            f"cannot build a valid sandbox name from role={role_name!r} project={project_name!r} task={task_id!r}"
        )
    if len(name) > MAX_SANDBOX_NAME_LENGTH:
        raise FoundryError(
            f"sandbox name {name!r} is over {MAX_SANDBOX_NAME_LENGTH} characters; shorten the project or task name"
        )
    return name


def _project_checkout_path(project_name: str) -> str:
    return f"{SANDBOX_WORK_PATH}/{_slug(project_name)}"


def _notes_checkout_path(project_name: str) -> str:
    return f"{_project_checkout_path(project_name)}-notes"


def build_env_file(
    *,
    sandbox_name: str,
    workspace_path: Path,
    agent_kit_path: Path,
    repo_url: str,
    role_name: str,
    task_id: str,
    project_name: str,
    agent_name: str = "claude",
) -> EnvFile:
    """The sbxenv.yaml structure, built but not written.

    ``workspace_path`` is an empty temporary directory: sbx requires a primary
    workspace before it accepts additional ones, but nothing goes in it. The
    agent kit is mounted read-only; the project is cloned inside the sandbox
    by session-init.
    """
    return {
        "schemaVersion": "1",
        "name": sandbox_name,
        "agent": agent_name,
        "workspace": str(workspace_path),
        "additionalWorkspaces": [{"path": str(agent_kit_path), "readOnly": True}],
        "env": {
            AGENT_ROLE_VAR: role_name,
            AGENT_TASK_VAR: task_id,
            AGENT_KIT_DIR_VAR: str(agent_kit_path),
            AGENT_REPO_URL_VAR: repo_url,
            AGENT_PROJECT_DIR_VAR: _project_checkout_path(project_name),
            AGENT_NOTES_DIR_VAR: _notes_checkout_path(project_name),
        },
    }


def workspace_path(env_file: EnvFile) -> Path:
    return Path(env_file["workspace"])


def agent_kit_path(env_file: EnvFile) -> Path:
    return Path(env_file["additionalWorkspaces"][0]["path"])


def create_session(session_path: Path, env_file: EnvFile, **record: Any) -> None:
    """Create the session directory with its sbxenv.yaml and session.yaml.

    Refuses if the directory already exists, so an existing sandbox's
    environment file is never rewritten.
    """
    try:
        session_path.mkdir(parents=True)
    except FileExistsError:
        raise FoundryError(f"session directory {session_path} already exists") from None
    yaml_io.dump(session_path / ENV_FILE_NAME, env_file)
    yaml_io.dump(session_path / RECORD_FILE_NAME, {**record, "launches": []})


def read_env_file(session_path: Path) -> EnvFile:
    env_file_path = session_path / ENV_FILE_NAME
    env_file = yaml_io.load(env_file_path)
    try:
        if not all(isinstance(env_file[key], str) for key in ("name", "workspace")):
            raise TypeError
        _ = env_file["env"][AGENT_ROLE_VAR], env_file["env"][AGENT_TASK_VAR]
        _ = env_file["additionalWorkspaces"][0]["path"]
    except (TypeError, KeyError, IndexError):
        raise FoundryError(f"{env_file_path} is not a foundry sandbox environment file") from None
    return cast(EnvFile, env_file)


def _read_record(session_path: Path) -> dict[str, Any]:
    record_path = session_path / RECORD_FILE_NAME
    record = yaml_io.load(record_path)
    if not isinstance(record, dict):
        raise FoundryError(f"{record_path} is not a session record")
    return record


def record_launch(session_path: Path, *, launched_at: datetime, fresh: bool) -> None:
    """Append one launch to session.yaml, keeping everything already there."""
    record = _read_record(session_path)
    launches = record.get("launches") or []
    record["launches"] = [*launches, {"at": launched_at.isoformat(timespec="seconds"), "fresh": fresh}]
    yaml_io.dump(session_path / RECORD_FILE_NAME, record)
