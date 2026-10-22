"""Sessions: one directory per sandbox, holding its sandbox definition and record.

``sessions/<sandbox>/`` holds the sandbox definition, written once when the
sandbox is first launched (agent_sandbox.definition knows its format), and
``session.yaml``, which records when it was created and each launch since:
the launcher hands over to sbx, so it never learns whether a launch got as
far as the agent.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from foundry import yaml_io
from foundry.agent_sandbox import SandboxDefinition
from foundry.agent_sandbox.definition import write as write_definition
from foundry.errors import FoundryError

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

# A task id becomes the git branch task/<id>, so it must be a valid ref
# component as well as readable: WCF-0042, fix-login.2.
_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# Inside the sandbox: where session-init clones the project. Nothing on the
# host corresponds to this path; it assumes the template's `agent` user.
SANDBOX_WORK_PATH: Final = "/home/agent/work"


def _slug(text: str) -> str:
    return _SBX_UNSAFE_CHARACTERS.sub("-", text).strip("-").lower()


def ensure_valid_task_id(task_id: str) -> None:
    """Raise unless ``task_id`` is letters, digits, '.', '_' or '-', and makes a valid branch name."""
    if not _TASK_ID.fullmatch(task_id) or ".." in task_id or task_id.endswith((".", ".lock")):
        raise FoundryError(
            f"task id {task_id!r} is not valid: use letters, digits, '.', '_' and '-', "
            "starting with a letter or digit (e.g. WCF-0042)"
        )


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


def sandbox_definition(
    *,
    sandbox_name: str,
    workspace_dir: Path,
    agent_kit_dir: Path,
    repo_url: str,
    role_name: str,
    task_id: str,
    project_name: str,
) -> SandboxDefinition:
    """The definition for a new sandbox: the agent kit mounted, and the variables the kit's scripts read.

    ``workspace_dir`` is an empty temporary directory; the project is cloned
    inside the sandbox by session-init.
    """
    return SandboxDefinition(
        name=sandbox_name,
        workspace_dir=workspace_dir,
        agent_kit_dir=agent_kit_dir,
        variables={
            AGENT_ROLE_VAR: role_name,
            AGENT_TASK_VAR: task_id,
            AGENT_KIT_DIR_VAR: str(agent_kit_dir),
            AGENT_REPO_URL_VAR: repo_url,
            AGENT_PROJECT_DIR_VAR: _project_checkout_path(project_name),
            AGENT_NOTES_DIR_VAR: _notes_checkout_path(project_name),
        },
    )


def create_session(session_dir: Path, definition: SandboxDefinition, /, **record: Any) -> None:
    """Create the session directory with its sandbox definition and session.yaml.

    Refuses if the directory already exists, so an existing sandbox's
    definition is never rewritten.
    """
    try:
        session_dir.mkdir(parents=True)
    except FileExistsError:
        raise FoundryError(f"session directory {session_dir} already exists") from None
    write_definition(session_dir, definition)
    yaml_io.dump(session_dir / RECORD_FILE_NAME, {**record, "launches": []})


def require_same_sandbox(definition: SandboxDefinition, *, role_name: str, task_id: str, repo_url: str) -> None:
    """Raise unless the existing sandbox is for this role, task and repository.

    Sandbox names are slugs, so different launches can share one: role dev on
    project foundry, task test-1, and on project foundry-test, task 1, are both
    dev-foundry-test-1. Re-attaching would then work on the other one's task.
    """
    expected = {AGENT_ROLE_VAR: role_name, AGENT_TASK_VAR: task_id, AGENT_REPO_URL_VAR: repo_url}
    found = {key: definition.variables.get(key) for key in expected}
    if found != expected:
        recorded = ", ".join(f"{key}={value!r}" for key, value in found.items())
        raise FoundryError(
            f"sandbox {definition.name} already exists for a different role, task or repository ({recorded}); "
            "either its name collides with this one, so use a task id that gives a different name, "
            "or the project's url has changed since, so remove the sandbox and "
            f"sessions/{definition.name}/ to start over."
        )


def _read_record(session_path: Path) -> dict[str, Any]:
    record_path = session_path / RECORD_FILE_NAME
    record = yaml_io.load(record_path)
    if not isinstance(record, dict):
        raise FoundryError(f"{record_path} is not a session record")
    return record


def record_launch(session_path: Path, *, launched_at: datetime) -> None:
    """Append one launch attempt to session.yaml, keeping everything already there.

    Recorded before the sandbox is prepared, so it includes launches that then
    failed: the launcher replaces itself with sbx and can't record success.
    """
    record = _read_record(session_path)
    launches = record.get("launches") or []
    record["launches"] = [*launches, {"at": launched_at.isoformat(timespec="seconds")}]
    yaml_io.dump(session_path / RECORD_FILE_NAME, record)
