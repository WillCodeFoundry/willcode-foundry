"""Sessions: one directory per sandbox, holding its sandbox definition and workspace.

``sessions/<sandbox>/`` holds the sandbox definition, written once when the
sandbox is first launched (SandboxDefinition knows its format), and the
empty ``workspace/`` directory sbx requires as the sandbox's primary
workspace. ``open_or_create`` is the whole interface: it names the sandbox,
creates its session the first time, and on every later launch reads the
definition back and refuses one written for another role, task or repository.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from foundry import paths
from foundry.agent_sandbox import SandboxDefinition
from foundry.config import Project, Role
from foundry.errors import FoundryError
from foundry.task import NOTES_BRANCH, NOTES_ROOT, Task

# sbx accepts letters, digits, '.', '+', '-'. The name also names an
# ssh-agent socket, whose path length is limited.
MAX_SANDBOX_NAME_LENGTH: Final = 64
_SBX_UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9.+-]+")

# Inside the sandbox: where session-init clones the project. Nothing on the
# host corresponds to this path; it assumes the template's `agent` user.
SANDBOX_WORK_DIR: Final = "/home/agent/work"


@dataclass(frozen=True)
class Session:
    """One sandbox's session: its directory and the sandbox definition in it."""

    dir: Path
    definition: SandboxDefinition
    created: bool
    """True when this call created the session, or finished one a stopped launch left without its definition."""

    @property
    def init_command(self) -> tuple[str, ...]:
        """session-init, from the agent kit this sandbox was created with.

        sbx fixes mounts when it creates a sandbox, so this is the kit recorded
        in the definition, not the foundry's current one: a moved foundry still
        finds the kit its existing sandboxes mount.
        """
        return (str(self.definition.agent_kit_dir / paths.SESSION_INIT_RELATIVE_PATH),)


def open_or_create(foundry_root: Path, *, project: Project, role: Role, task: Task) -> Session:
    """The session for this role on this task in this project, created the first time.

    Raises FoundryError if the sandbox name would be too long, if the session
    directory exists without its definition but holds more than an empty
    workspace, or if the existing definition was written for another role,
    task or repository.
    """
    sandbox_name = _sandbox_name(role.name, project.name, task)
    session_dir = paths.session_dir(foundry_root, sandbox_name)
    created = not (session_dir / SandboxDefinition.FILE_NAME).is_file()
    if created:
        _create(
            session_dir,
            _sandbox_definition(
                sandbox_name=sandbox_name,
                workspace_dir=paths.workspace_dir(foundry_root, sandbox_name),
                agent_kit_dir=paths.agent_kit_dir(foundry_root),
                repo_url=project.url,
                role_name=role.name,
                task=task,
                project_name=project.name,
            ),
        )
    definition = SandboxDefinition.read(session_dir)
    _require_same_sandbox(definition, role_name=role.name, task=task, repo_url=project.url)
    return Session(dir=session_dir, definition=definition, created=created)


def _slug(text: str) -> str:
    return _SBX_UNSAFE_CHARACTERS.sub("-", text).strip("-").lower()


def _sandbox_name(role_name: str, project_name: str, task: Task) -> str:
    """Stable per (role, project, task), so a rerun re-attaches: dev-tkt-store-wcf-0042."""
    name = "-".join(_slug(part) for part in (role_name, project_name, task.id))
    if len(name) > MAX_SANDBOX_NAME_LENGTH:
        raise FoundryError(
            f"sandbox name {name!r} is over {MAX_SANDBOX_NAME_LENGTH} characters; shorten the project or task name"
        )
    return name


def _sandbox_definition(
    *,
    sandbox_name: str,
    workspace_dir: Path,
    agent_kit_dir: Path,
    repo_url: str,
    role_name: str,
    task: Task,
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
            "AGENT_TASK": task.id,
            "AGENT_KIT_DIR": str(agent_kit_dir),
            "AGENT_REPO_URL": repo_url,
            "AGENT_PROJECT_DIR": project_dir,
            "AGENT_NOTES_DIR": f"{project_dir}-notes",
            # A task's names, so the kit and the agent's instructions spell none out.
            # The notes paths are relative to a checkout's root, as git reports paths.
            "AGENT_TASK_BRANCH": task.branch,
            "AGENT_NOTES_BRANCH": NOTES_BRANCH,
            "AGENT_NOTES_ROOT": NOTES_ROOT,
            "AGENT_TASK_NOTES": task.notes_dir,
            "AGENT_TASK_FILE": task.task_file,
        },
    )


def _create(session_dir: Path, definition: SandboxDefinition) -> None:
    """Create the session directory with its empty workspace, then the sandbox definition.

    The definition is written last, so a session with one is complete. A
    directory without one, left by a launch that stopped before writing it,
    is finished if it holds nothing but an empty workspace, and refused if it
    holds anything else, so nothing it holds is overwritten or mounted.
    """
    if session_dir.exists() and not _holds_only_an_empty_workspace(session_dir, definition.workspace_dir):
        raise FoundryError(
            f"session directory {session_dir} exists without its {SandboxDefinition.FILE_NAME} "
            "and holds more than an empty workspace/; check what is in it, delete it, and launch again"
        )
    definition.workspace_dir.mkdir(parents=True, exist_ok=True)
    definition.write(session_dir)


def _holds_only_an_empty_workspace(session_dir: Path, workspace_dir: Path) -> bool:
    if not session_dir.is_dir():
        return False
    return all(
        entry == workspace_dir and entry.is_dir() and not any(entry.iterdir()) for entry in session_dir.iterdir()
    )


def _require_same_sandbox(definition: SandboxDefinition, *, role_name: str, task: Task, repo_url: str) -> None:
    """Raise unless the existing sandbox is for this role, task and repository.

    Sandbox names are slugs, so different launches can share one: role dev on
    project foundry, task test-1, and on project foundry-test, task 1, are both
    dev-foundry-test-1. Re-attaching would then work on the other one's task.
    """
    expected = {"AGENT_ROLE": role_name, "AGENT_TASK": task.id, "AGENT_REPO_URL": repo_url}
    found = {key: definition.variables.get(key) for key in expected}
    if found != expected:
        recorded = ", ".join(f"{key}={value!r}" for key, value in found.items())
        raise FoundryError(
            f"sandbox {definition.name} already exists for a different role, task or repository ({recorded}); "
            "either its name collides with this one, so use a task id that gives a different name, "
            "or the project's url has changed since, so remove the sandbox and "
            f"sessions/{definition.name}/ to start over."
        )
