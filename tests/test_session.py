"""Sessions, through open_or_create against a foundry root under tmp_path; and the session variables."""

import dataclasses
import shutil
from pathlib import Path
from typing import Any

import pytest

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit
from foundry import session
from foundry.agent_sandbox import SandboxDefinition
from foundry.config import Project, Role
from foundry.errors import FoundryError
from foundry.task import Task

TKT_STORE = Project(name="tkt-store", url="git@github.com:o/tkt-store.git")
DEV = Role(name="dev", ssh_key_path=Path("/foundry/secrets/ssh/dev"), github_token_path=None)


def test_the_first_open_creates_the_session_with_its_workspace_inside(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("wcf-0042"))

    session_dir = tmp_path / "sessions" / "dev-tkt-store-wcf-0042"
    assert opened.dir == session_dir
    assert opened.definition == SandboxDefinition.read(session_dir)
    assert opened.definition.name == "dev-tkt-store-wcf-0042"
    assert opened.definition.workspace_dir == session_dir / "workspace"
    assert opened.definition.workspace_dir.is_dir()
    assert opened.definition.agent_kit_dir == tmp_path / "agent-kit"
    assert sorted(path.name for path in session_dir.iterdir()) == ["sbxenv.yaml", "workspace"]


def test_the_definition_carries_the_variables_the_agent_kit_reads(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("wcf-0042"))

    assert opened.definition.variables == {
        "AGENT_ROLE": "dev",
        "AGENT_TASK_ID": "wcf-0042",
        "AGENT_KIT_DIR": str(tmp_path / "agent-kit"),
        "AGENT_REPO_URL": "git@github.com:o/tkt-store.git",
        "AGENT_CODE_CHECKOUT_DIR": "/home/agent/work/tkt-store",
        "AGENT_NOTES_CHECKOUT_DIR": "/home/agent/work/tkt-store-notes",
        "AGENT_TASK_BRANCH": "task/wcf-0042",
        "AGENT_NOTES_BRANCH": "agent-notes",
        "AGENT_NOTES_ROOT": ".agent",
        "AGENT_TASK_NOTES_DIR": ".agent/tasks/open/wcf-0042",
        "AGENT_TASK_FILE": ".agent/tasks/open/wcf-0042/TASK.md",
    }


def test_sandbox_names_are_sbx_safe(tmp_path: Path) -> None:
    project = Project(name="Tkt Store!", url="git@github.com:o/tkt-store.git")
    opened = session.open_or_create(tmp_path, project=project, role=DEV, task=Task.as_open("tst-0001"))
    assert opened.dir.name == "dev-tkt-store-tst-0001"


def test_a_sandbox_name_over_the_limit_is_refused(tmp_path: Path) -> None:
    project = Project(name="p" * 60, url="git@github.com:o/p.git")
    with pytest.raises(FoundryError, match="over 64 characters"):
        session.open_or_create(tmp_path, project=project, role=DEV, task=Task.as_open("wcf-0042"))
    assert not (tmp_path / "sessions").exists()


def test_a_reopen_reuses_the_definition_unchanged(tmp_path: Path) -> None:
    first = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("wcf-0042"))
    definition_path = first.dir / SandboxDefinition.FILE_NAME
    before = definition_path.read_text()

    second = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("wcf-0042"))

    assert (second.dir, second.definition) == (first.dir, first.definition)
    assert definition_path.read_text() == before


@pytest.mark.parametrize(
    ("project", "role", "task"),
    [
        # Slugs collide: dev on foundry, and dev on Foundry, task tst-0001.
        (Project(name="Foundry", url="git@github.com:o/Foundry.git"), DEV, Task.as_open("tst-0001")),
        # The project's url changed since the session was created.
        (Project(name="foundry", url="git@github.com:o/moved.git"), DEV, Task.as_open("tst-0001")),
    ],
)
def test_a_sandbox_for_another_role_task_or_repository_is_refused(
    tmp_path: Path, project: Project, role: Role, task: Task
) -> None:
    foundry = Project(name="foundry", url="git@github.com:o/foundry.git")
    session.open_or_create(tmp_path, project=foundry, role=DEV, task=Task.as_open("tst-0001"))

    with pytest.raises(FoundryError, match="already exists for a different role, task or repository"):
        session.open_or_create(tmp_path, project=project, role=role, task=task)


def test_the_init_command_runs_the_agent_kit_of_this_foundry(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))

    assert opened.launch_request().init_command == AgentKit(tmp_path / "agent-kit").runtime_command("session-init")


def test_a_copied_foundry_cant_open_the_originals_sandbox(tmp_path: Path) -> None:
    """sbx fixed the mount when it created the sandbox, on the original's kit: a copy launching it would rebuild
    the runtime under the original's sandboxes."""
    original, copy = tmp_path / "original", tmp_path / "copy"
    session.open_or_create(original, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))
    shutil.copytree(original, copy)
    (original / "agent-kit").mkdir()

    with pytest.raises(FoundryError) as refused:
        session.open_or_create(copy, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))

    assert str(refused.value) == (
        f"dev-tkt-store-tst-0001 mounts the agent kit at {original / 'agent-kit'}, not this foundry's "
        f"({copy / 'agent-kit'}): launch it from the foundry there, "
        f"or {session.recreate_hint('dev-tkt-store-tst-0001')}"
    )


def test_the_sandbox_of_a_moved_foundry_needs_recreating(tmp_path: Path) -> None:
    """The kit the sandbox mounts is gone with the move: sbx can't mount it again."""
    session.open_or_create(tmp_path / "before", project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))
    (tmp_path / "before").rename(tmp_path / "after")

    with pytest.raises(FoundryError) as refused:
        session.open_or_create(tmp_path / "after", project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))

    assert str(refused.value) == (
        f"dev-tkt-store-tst-0001 mounts the agent kit at {tmp_path / 'before' / 'agent-kit'}, which is gone: "
        f"{session.recreate_hint('dev-tkt-store-tst-0001')}"
    )


def test_the_recreate_hint_points_at_the_readme() -> None:
    assert session.recreate_hint("s") == (
        "recreate it: `sbx env rm --force sessions/s`, delete sessions/s/, and launch again "
        "(see Recreating a sandbox in the README)"
    )


def test_a_session_left_without_its_definition_is_finished(tmp_path: Path) -> None:
    (tmp_path / "sessions" / "dev-tkt-store-wcf-0042" / "workspace").mkdir(parents=True)

    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("wcf-0042"))

    assert opened.definition == SandboxDefinition.read(opened.dir)


@pytest.mark.parametrize("leftover", ["workspace/notes.txt", "notes.txt"])
def test_a_session_left_without_its_definition_but_holding_files_is_refused(tmp_path: Path, leftover: str) -> None:
    session_dir = tmp_path / "sessions" / "dev-tkt-store-wcf-0042"
    (session_dir / "workspace").mkdir(parents=True)
    (session_dir / leftover).write_text("x")

    with pytest.raises(FoundryError, match="holds more than an empty workspace"):
        session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("wcf-0042"))
    assert not (session_dir / SandboxDefinition.FILE_NAME).exists()


def test_a_file_where_the_session_directory_goes_is_refused(tmp_path: Path) -> None:
    session_path = tmp_path / "sessions" / "dev-tkt-store-wcf-0042"
    session_path.parent.mkdir()
    session_path.write_text("x")

    with pytest.raises(FoundryError, match="holds more than an empty workspace"):
        session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("wcf-0042"))
    assert session_path.read_text() == "x"


# --- session variables ---------------------------------------------------------


def test_the_definition_holds_the_session_variables_for_its_role_and_task(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("wcf-0042"))

    assert opened.definition.variables == {
        "AGENT_ROLE": "dev",
        "AGENT_TASK_ID": "wcf-0042",
        "AGENT_KIT_DIR": str(tmp_path / "agent-kit"),
        "AGENT_REPO_URL": "git@github.com:o/tkt-store.git",
        "AGENT_CODE_CHECKOUT_DIR": "/home/agent/work/tkt-store",
        "AGENT_NOTES_CHECKOUT_DIR": "/home/agent/work/tkt-store-notes",
        "AGENT_TASK_BRANCH": "task/wcf-0042",
        "AGENT_NOTES_BRANCH": "agent-notes",
        "AGENT_NOTES_ROOT": ".agent",
        "AGENT_TASK_NOTES_DIR": ".agent/tasks/open/wcf-0042",
        "AGENT_TASK_FILE": ".agent/tasks/open/wcf-0042/TASK.md",
    }


def rewrite_variables(session_dir: Path, change: dict[str, str | None]) -> None:
    """Rewrite a session's definition with some variables changed, or removed where None: an older foundry's."""
    definition = SandboxDefinition.read(session_dir)
    variables = {**definition.variables, **change}
    kept = {name: value for name, value in variables.items() if value is not None}
    dataclasses.replace(definition, variables=kept).write(session_dir)


def test_a_sandbox_created_without_a_variable_is_refused_naming_it(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))
    rewrite_variables(opened.dir, {"AGENT_TASK_FILE": None, "AGENT_NOTES_ROOT": None})

    with pytest.raises(FoundryError, match=r"missing AGENT_NOTES_ROOT, AGENT_TASK_FILE\).*sbx env rm --force"):
        session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))


def test_a_sandbox_created_with_another_name_is_refused_naming_both(tmp_path: Path) -> None:
    """Its hooks would guard the old branch, so it is recreated rather than reused."""
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))
    rewrite_variables(opened.dir, {"AGENT_NOTES_BRANCH": "notes"})

    with pytest.raises(FoundryError, match="AGENT_NOTES_BRANCH='notes', now 'agent-notes'"):
        session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))


def variables(**change: object) -> contract.SessionVariables:
    """The session variables for role dev on task tst-0001 of repository u, with ``change`` made."""
    given: dict[str, Any] = {
        "role_name": "dev",
        "task": Task.as_open("tst-0001"),
        "repo_url": "u",
        "agent_kit_dir": Path("/kit"),
        "code_checkout_dir": Path("/w/p"),
    }
    return session.session_variables(**{**given, **change})


def test_the_same_sandbox_is_the_same_role_task_and_repository_whatever_the_paths() -> None:
    assert session.is_same_sandbox(variables(), variables(agent_kit_dir=Path("/moved"), code_checkout_dir=Path("/w/q")))
    for other in (variables(role_name="qa"), variables(task=Task.as_open("tst-0002")), variables(repo_url="v")):
        assert not session.is_same_sandbox(variables(), other)


def test_a_sandbox_created_with_an_empty_variable_is_refused_naming_it(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))
    rewrite_variables(opened.dir, {"AGENT_REPO_URL": ""})

    with pytest.raises(FoundryError, match=r"missing AGENT_REPO_URL\)"):
        session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task.as_open("tst-0001"))
