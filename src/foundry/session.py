"""Sessions: the host-side record of one sandbox, kept in its session directory.

``sessions/<sandbox>/`` holds the sandbox definition, written once when the
sandbox is first launched (SandboxDefinition knows its format), and the
empty ``workspace/`` directory sbx requires as the sandbox's primary
workspace. The definition carries the session variables, the AGENT_*
variables the sandbox is created with (SessionVariables knows their names).
``open_or_create`` is the whole interface: it names the sandbox, creates its
session the first time, and on every later launch reads the definition back
and refuses one written for another role, task or repository.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit
from foundry import paths
from foundry.agent_sandbox import SandboxDefinition
from foundry.config import Project, Role
from foundry.errors import FoundryError
from foundry.task import NOTES_BRANCH, NOTES_ROOT, Task

# sbx accepts letters, digits, '.', '+', '-'. The name also names an
# ssh-agent socket, whose path length is limited.
MAX_SANDBOX_NAME_LENGTH: Final = 64
_SBX_UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9.+-]+")

SANDBOX_WORK_DIR: Final = f"/home/{contract.SANDBOX_USER}/work"
"""Inside the sandbox: where session-setup clones the project. Nothing on the host corresponds to it."""


@dataclass(frozen=True, kw_only=True)
class SessionVariables:
    """What a session's sandbox is told: the AGENT_* variables, as one value.

    Their names come from agent_runtime.contract, which the runtime reads them back with;
    AGENTS.md lists them, and tests/test_task_contract.py holds it and the kit to the contract.
    They are fixed when the sandbox is created: sbx never rewrites its definition.
    """

    role_name: str
    task: Task
    repo_url: str
    agent_kit_dir: Path
    """Where the agent kit is mounted, read-only: the same path inside the sandbox as on the host."""
    project_dir: str
    """The code checkout, inside the sandbox; the notes checkout sits beside it."""

    @property
    def notes_dir(self) -> str:
        """The notes checkout, inside the sandbox."""
        return f"{self.project_dir}-notes"

    def to_env(self) -> dict[str, str]:
        """The variables, by name, as the sandbox definition carries them."""
        return {
            contract.ROLE: self.role_name,
            contract.TASK: self.task.id,
            contract.KIT_DIR: str(self.agent_kit_dir),
            contract.REPO_URL: self.repo_url,
            contract.PROJECT_DIR: self.project_dir,
            contract.NOTES_DIR: self.notes_dir,
            contract.TASK_BRANCH: self.task.branch,
            contract.NOTES_BRANCH: NOTES_BRANCH,
            contract.NOTES_ROOT: NOTES_ROOT,
            contract.TASK_NOTES: self.task.notes_dir,
            contract.TASK_FILE: self.task.task_file,
        }

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "SessionVariables":
        """Read the variables back. ``from_env(v.to_env()) == v``.

        Raises FoundryError naming every variable that is missing, or that holds another value than
        this foundry would set for the same role, task and paths: a sandbox created before a name
        changed keeps the old one, and its kit would use it.
        """
        missing = [name for name in contract.NAMES if name not in env]
        if missing:
            raise FoundryError(f"missing {', '.join(missing)}")
        variables = cls(
            role_name=env[contract.ROLE],
            task=Task(env[contract.TASK]),
            repo_url=env[contract.REPO_URL],
            agent_kit_dir=Path(env[contract.KIT_DIR]),
            project_dir=env[contract.PROJECT_DIR],
        )
        differing = [
            f"{name}={env[name]!r}, now {value!r}" for name, value in variables.to_env().items() if env[name] != value
        ]
        if differing:
            raise FoundryError(f"other values: {'; '.join(differing)}")
        return variables

    def is_same_sandbox(self, other: "SessionVariables") -> bool:
        """Whether both are for the same role, task and repository; paths may differ, e.g. after the foundry moved."""
        return (self.role_name, self.task, self.repo_url) == (other.role_name, other.task, other.repo_url)


@dataclass(frozen=True, kw_only=True)
class Session:
    """One sandbox's session: its directory, the sandbox definition in it, and the variables that carries."""

    dir: Path
    definition: SandboxDefinition
    variables: SessionVariables
    """Read back from the definition, so it is what the sandbox was told, not what this launch would tell it."""
    created: bool
    """True when this call created the session, or finished one a stopped launch left without its definition."""

    @property
    def init_command(self) -> tuple[str, ...]:
        """The runtime's session-init, from the agent kit this sandbox was created with.

        sbx fixes mounts when it creates a sandbox, so this is the kit recorded
        in the definition, not the foundry's current one: a moved foundry still
        finds the kit its existing sandboxes mount.
        """
        return AgentKit(self.definition.agent_kit_dir).command("session-init")


def open_or_create(foundry_root: Path, *, project: Project, role: Role, task: Task) -> Session:
    """The session for this role on this task in this project, created the first time.

    Raises FoundryError if the sandbox name would be too long, if the session
    directory exists without its definition but holds more than an empty
    workspace, or if the existing definition was written for another role,
    task or repository.
    """
    sandbox_name = _sandbox_name(role_name=role.name, project_name=project.name, task=task)
    session_dir = paths.session_dir(foundry_root, sandbox_name)
    wanted = SessionVariables(
        role_name=role.name,
        task=task,
        repo_url=project.url,
        agent_kit_dir=paths.agent_kit_dir(foundry_root),
        project_dir=f"{SANDBOX_WORK_DIR}/{_slug(project.name)}",
    )
    created = not (session_dir / SandboxDefinition.FILE_NAME).is_file()
    if created:
        _create(
            session_dir,
            SandboxDefinition(
                name=sandbox_name,
                workspace_dir=paths.workspace_dir(foundry_root, sandbox_name),
                agent_kit_dir=wanted.agent_kit_dir,
                variables=wanted.to_env(),
            ),
        )
    definition = SandboxDefinition.read(session_dir)
    recorded = _recorded_variables(definition)
    _require_same_sandbox(definition.name, recorded=recorded, wanted=wanted)
    return Session(dir=session_dir, definition=definition, variables=recorded, created=created)


def _slug(text: str) -> str:
    return _SBX_UNSAFE_CHARACTERS.sub("-", text).strip("-").lower()


def _sandbox_name(*, role_name: str, project_name: str, task: Task) -> str:
    """Stable per (role, project, task), so a rerun re-attaches: dev-tkt-store-wcf-0042."""
    name = "-".join(_slug(part) for part in (role_name, project_name, task.id))
    if len(name) > MAX_SANDBOX_NAME_LENGTH:
        raise FoundryError(
            f"sandbox name {name!r} is over {MAX_SANDBOX_NAME_LENGTH} characters; shorten the project or task name"
        )
    return name


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


def _recorded_variables(definition: SandboxDefinition) -> SessionVariables:
    """The session variables the existing sandbox was created with; raises if they aren't this foundry's."""
    try:
        return SessionVariables.from_env(definition.variables)
    except FoundryError as error:
        raise FoundryError(
            f"sandbox {definition.name} was created with session variables this foundry doesn't set ({error}), "
            "so its agent kit would use them; remove it with "
            f"`sbx env rm --force sessions/{definition.name}`, delete sessions/{definition.name}/, and launch again"
        ) from None


def _require_same_sandbox(sandbox_name: str, *, recorded: SessionVariables, wanted: SessionVariables) -> None:
    """Raise unless the existing sandbox is for this role, task and repository.

    Sandbox names are slugs, so different launches can share one: role dev on
    project foundry, task test-1, and on project foundry-test, task 1, are both
    dev-foundry-test-1. Re-attaching would then work on the other one's task.
    """
    if not recorded.is_same_sandbox(wanted):
        raise FoundryError(
            f"sandbox {sandbox_name} already exists for a different role, task or repository "
            f"(role {recorded.role_name!r}, task {recorded.task.id!r}, repository {recorded.repo_url!r}); "
            "either its name collides with this one, so use a task id that gives a different name, "
            "or the project's url has changed since, so remove the sandbox and "
            f"sessions/{sandbox_name}/ to start over."
        )
