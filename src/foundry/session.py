"""Sessions: the host-side record of one sandbox, kept in its session directory.

``sessions/<sandbox>/`` holds the sandbox definition, written once when the
sandbox is first launched (SandboxDefinition knows its format), and the
empty ``workspace/`` directory sbx requires as the sandbox's primary
workspace. The definition carries the session variables, the AGENT_*
variables the sandbox is created with (``session_variables`` derives them; agent_runtime.contract names them).
``open_or_create`` names the sandbox, creates its session the first time, and on
every later launch reads the definition back and refuses one written for another
role, task, repository or agent kit. ``Session.launch_request`` is what a launch
asks agent_sandbox for. ``recreate_hint`` says how to start a sandbox over.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit
from foundry import paths
from foundry.agent_sandbox import MAX_SANDBOX_NAME_LENGTH, LaunchRequest, SandboxDefinition, is_valid_sandbox_name
from foundry.config import Project, Role
from foundry.errors import FoundryError
from foundry.task import NOTES_BRANCH, NOTES_ROOT, Task

_LOGGER = logging.getLogger(__name__)

_UNSLUGGED = re.compile(r"[^A-Za-z0-9.+-]+")
"""What a sandbox name's parts lose: anything but letters, digits, '.', '+' and '-'."""

_SANDBOX_WORK_DIR: Final = Path(f"/home/{contract.SANDBOX_USER}/work")
"""Inside the sandbox: where session-setup clones the project. Nothing on the host corresponds to it."""


def session_variables(
    *, role_name: str, task: Task, repo_url: str, agent_kit_dir: Path, code_checkout_dir: Path
) -> contract.SessionVariables:
    """What a sandbox for this role on this task is told: five values, and the rest derived from them.

    AGENTS.md lists the variables, and tests/test_task_contract.py holds it and the kit to the contract.
    They are fixed when the sandbox is created, since sbx never rewrites its definition.

    ``agent_kit_dir`` is mounted read-only at the same path inside the sandbox as on the host.
    ``code_checkout_dir`` is inside the sandbox, and the notes checkout sits beside it.
    """
    return contract.SessionVariables(
        agent_role=role_name,
        agent_task_id=task.id,
        agent_kit_dir=agent_kit_dir,
        agent_repo_url=repo_url,
        agent_code_checkout_dir=code_checkout_dir,
        agent_notes_checkout_dir=code_checkout_dir.with_name(f"{code_checkout_dir.name}-notes"),
        agent_task_branch=task.branch,
        agent_notes_branch=NOTES_BRANCH,
        agent_notes_root=NOTES_ROOT,
        agent_task_notes_dir=task.task_notes_dir,
        agent_task_file=task.task_file,
    )


def is_same_sandbox(recorded: contract.SessionVariables, wanted: contract.SessionVariables) -> bool:
    """Whether both are for the same role, task and repository: what a sandbox's name stands for."""
    return (recorded.agent_role, recorded.agent_task_id, recorded.agent_repo_url) == (
        wanted.agent_role,
        wanted.agent_task_id,
        wanted.agent_repo_url,
    )


@dataclass(frozen=True, kw_only=True)
class Session:
    """One sandbox's session, opened for one role: its directory and the sandbox definition in it."""

    dir: Path
    definition: SandboxDefinition
    role: Role
    """The role this launch is for: its key, token and model are read at each launch, not recorded."""

    def launch_request(self) -> LaunchRequest:
        """What agent_sandbox needs to launch this session's sandbox. Reads and writes nothing.

        The agent kit is the definition's, which open_or_create checked is this foundry's.
        """
        return LaunchRequest(
            definition_dir=self.dir,
            ssh_key_path=self.role.ssh_key_path,
            init_command=AgentKit(self.definition.agent_kit_dir).runtime_command("session-init"),
            github_token_path=self.role.github_token_path,
            model=self.role.model,
        )


def open_or_create(foundry_root: Path, *, project: Project, role: Role, task: Task) -> Session:
    """The session for this role on this task in this project, created, and shown as progress, the first time.

    Raises FoundryError if the sandbox name would be too long, if the session
    directory exists without its definition but holds more than an empty
    workspace, or if the existing definition was written for another role,
    task or repository, or mounts another foundry's agent kit.
    """
    sandbox_name = _sandbox_name(role_name=role.name, project_name=project.name, task=task)
    session_dir = paths.session_dir(foundry_root, sandbox_name)
    wanted = _wanted_variables(foundry_root, project, role, task)
    created = not (session_dir / SandboxDefinition.FILE_NAME).is_file()
    if created:
        _create_session_dir(session_dir, _definition(foundry_root, sandbox_name, wanted))
    definition = SandboxDefinition.read(session_dir)
    recorded = _recorded_variables(definition)
    _require_same_sandbox(definition.name, recorded=recorded, wanted=wanted)
    _require_own_kit(definition.name, recorded=recorded.agent_kit_dir, own=wanted.agent_kit_dir)
    if created:
        _LOGGER.info("session:   %s (new)", session_dir)
    return Session(dir=session_dir, definition=definition, role=role)


def _wanted_variables(foundry_root: Path, project: Project, role: Role, task: Task) -> contract.SessionVariables:
    """What this foundry would tell a new sandbox for this role on this task."""
    return session_variables(
        role_name=role.name,
        task=task,
        repo_url=project.url,
        agent_kit_dir=paths.agent_kit_dir(foundry_root),
        code_checkout_dir=_SANDBOX_WORK_DIR / _slug(project.name),
    )


def _definition(foundry_root: Path, sandbox_name: str, variables: contract.SessionVariables) -> SandboxDefinition:
    return SandboxDefinition(
        name=sandbox_name,
        workspace_dir=paths.workspace_dir(foundry_root, sandbox_name),
        agent_kit_dir=variables.agent_kit_dir,
        variables=variables.to_env(),
    )


def _slug(text: str) -> str:
    return _UNSLUGGED.sub("-", text).strip("-").lower()


def _sandbox_name(*, role_name: str, project_name: str, task: Task) -> str:
    """Stable per (role, project, task), so a rerun re-attaches: dev-tkt-store-wcf-0042."""
    name = "-".join(_slug(part) for part in (role_name, project_name, task.id))
    if not is_valid_sandbox_name(name):
        raise FoundryError(
            f"sandbox name {name!r} is over {MAX_SANDBOX_NAME_LENGTH} characters; shorten the project or task name"
        )
    return name


def _create_session_dir(session_dir: Path, definition: SandboxDefinition) -> None:
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


def _recorded_variables(definition: SandboxDefinition) -> contract.SessionVariables:
    """The session variables the existing sandbox was created with; raises if they aren't this foundry's.

    They are this foundry's when none is missing, and each holds what session_variables derives from the recorded
    role, task, repository and paths. A sandbox created before a name changed keeps the old one, and its kit would
    use it.
    """
    env = definition.variables
    if missing := contract.missing_names(env, contract.NAMES):
        raise _not_this_foundrys(definition.name, f"missing {', '.join(missing)}")
    recorded = contract.read_session_variables(env)
    derived = session_variables(
        role_name=recorded.agent_role,
        task=Task.as_open(recorded.agent_task_id),
        repo_url=recorded.agent_repo_url,
        agent_kit_dir=recorded.agent_kit_dir,
        code_checkout_dir=recorded.agent_code_checkout_dir,
    )
    if differing := [
        f"{name}={env[name]!r}, now {value!r}" for name, value in derived.to_env().items() if env[name] != value
    ]:
        raise _not_this_foundrys(definition.name, f"other values: {'; '.join(differing)}")
    return recorded


def _not_this_foundrys(sandbox_name: str, reason: str) -> FoundryError:
    return FoundryError(
        f"sandbox {sandbox_name} was created with session variables this foundry doesn't set ({reason}), "
        f"so its agent kit would use them; {recreate_hint(sandbox_name)}"
    )


def _require_same_sandbox(
    sandbox_name: str, *, recorded: contract.SessionVariables, wanted: contract.SessionVariables
) -> None:
    """Raise unless the existing sandbox is for this role, task and repository.

    Sandbox names are slugs, so different launches can share one: role dev on
    project foundry, task test-1, and on project foundry-test, task 1, are both
    dev-foundry-test-1. Re-attaching would then work on the other one's task.
    """
    if not is_same_sandbox(recorded, wanted):
        raise FoundryError(
            f"sandbox {sandbox_name} already exists for a different role, task or repository "
            f"(role {recorded.agent_role!r}, task {recorded.agent_task_id!r}, repository {recorded.agent_repo_url!r}); "
            "either its name collides with this one, so use a task id that gives a different name, "
            f"or the project's url has changed since, so {recreate_hint(sandbox_name)}"
        )


def _require_own_kit(sandbox_name: str, *, recorded: Path, own: Path) -> None:
    """Raise unless the sandbox mounts this foundry's agent kit. sbx fixed the mount when it created the sandbox:
    a copied foundry would rebuild the original's runtime under the original's sandboxes, and a moved one's
    recorded kit is gone."""
    if recorded.resolve() == own.resolve():
        return
    if recorded.is_dir():
        raise FoundryError(
            f"{sandbox_name} mounts the agent kit at {recorded}, not this foundry's ({own}): "
            f"launch it from the foundry there, or {recreate_hint(sandbox_name)}"
        )
    raise FoundryError(
        f"{sandbox_name} mounts the agent kit at {recorded}, which is gone: {recreate_hint(sandbox_name)}"
    )


def recreate_hint(sandbox_name: str) -> str:
    """How to start a sandbox over, for a message that ends by saying so."""
    return (
        f"recreate it: `sbx env rm --force sessions/{sandbox_name}`, delete sessions/{sandbox_name}/, and launch "
        "again (see Recreating a sandbox in the README)"
    )
