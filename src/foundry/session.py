"""Sessions: one directory per sandbox, holding its sandbox definition and workspace.

``sessions/<sandbox>/`` holds the sandbox definition, written once when the
sandbox is first launched (SandboxDefinition knows its format), and the
empty ``workspace/`` directory sbx requires as the sandbox's primary
workspace.
"""

import re
from pathlib import Path
from typing import Final

from foundry.agent_sandbox import SandboxDefinition
from foundry.errors import FoundryError

# sbx accepts letters, digits, '.', '+', '-'. The name also names an
# ssh-agent socket, whose path length is limited.
MAX_SANDBOX_NAME_LENGTH: Final = 64
_SBX_UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9.+-]+")

# A task id becomes the git branch task/<id>, so it must be a valid ref
# component as well as readable: WCF-0042, fix-login.2.
_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# Inside the sandbox: where session-init clones the project. Nothing on the
# host corresponds to this path; it assumes the template's `agent` user.
SANDBOX_WORK_DIR: Final = "/home/agent/work"


def _slug(text: str) -> str:
    return _SBX_UNSAFE_CHARACTERS.sub("-", text).strip("-").lower()


def require_valid_task_id(task_id: str) -> None:
    """Raise unless ``task_id`` is letters, digits, '.', '_' or '-', and makes a valid branch name."""
    if not _TASK_ID.fullmatch(task_id) or ".." in task_id or task_id.endswith((".", ".lock")):
        raise FoundryError(
            f"task id {task_id!r} is not valid: use letters, digits, '.', '_' and '-', "
            "starting with a letter or digit (e.g. WCF-0042)"
        )


def sandbox_name(role_name: str, project_name: str, task_id: str) -> str:
    """Stable per (role, project, task), so a rerun re-attaches: dev-tkt-store-wcf-0042."""
    name = "-".join(_slug(part) for part in (role_name, project_name, task_id))
    if len(name) > MAX_SANDBOX_NAME_LENGTH:
        raise FoundryError(
            f"sandbox name {name!r} is over {MAX_SANDBOX_NAME_LENGTH} characters; shorten the project or task name"
        )
    return name


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

    ``workspace_dir`` is the session's empty workspace; the project is cloned
    inside the sandbox by session-init, into the checkout directories below.
    The variable names are the contract with AGENTS.md and the kit's scripts.
    """
    project_dir = f"{SANDBOX_WORK_DIR}/{_slug(project_name)}"
    return SandboxDefinition(
        name=sandbox_name,
        workspace_dir=workspace_dir,
        agent_kit_dir=agent_kit_dir,
        variables={
            "AGENT_ROLE": role_name,
            "AGENT_TASK": task_id,
            "AGENT_KIT_DIR": str(agent_kit_dir),
            "AGENT_REPO_URL": repo_url,
            "AGENT_PROJECT_DIR": project_dir,
            "AGENT_NOTES_DIR": f"{project_dir}-notes",
        },
    )


def create(session_dir: Path, definition: SandboxDefinition) -> None:
    """Create the session directory with its sandbox definition and empty workspace.

    Refuses if the directory already exists, so an existing sandbox's
    definition is never rewritten.
    """
    try:
        session_dir.mkdir(parents=True)
    except FileExistsError:
        raise FoundryError(f"session directory {session_dir} already exists") from None
    definition.workspace_dir.mkdir()
    definition.write(session_dir)


def require_same_sandbox(definition: SandboxDefinition, *, role_name: str, task_id: str, repo_url: str) -> None:
    """Raise unless the existing sandbox is for this role, task and repository.

    Sandbox names are slugs, so different launches can share one: role dev on
    project foundry, task test-1, and on project foundry-test, task 1, are both
    dev-foundry-test-1. Re-attaching would then work on the other one's task.
    """
    expected = {"AGENT_ROLE": role_name, "AGENT_TASK": task_id, "AGENT_REPO_URL": repo_url}
    found = {key: definition.variables.get(key) for key in expected}
    if found != expected:
        recorded = ", ".join(f"{key}={value!r}" for key, value in found.items())
        raise FoundryError(
            f"sandbox {definition.name} already exists for a different role, task or repository ({recorded}); "
            "either its name collides with this one, so use a task id that gives a different name, "
            "or the project's url has changed since, so remove the sandbox and "
            f"sessions/{definition.name}/ to start over."
        )
