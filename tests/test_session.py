"""Sessions, through open_or_create against a foundry root under tmp_path."""

from pathlib import Path

import pytest

from foundry import session
from foundry.agent_sandbox import SandboxDefinition
from foundry.config import Project, Role
from foundry.errors import FoundryError
from foundry.task import Task

TKT_STORE = Project(name="tkt-store", url="git@github.com:o/tkt-store.git")
DEV = Role(name="dev")


def test_the_first_open_creates_the_session_with_its_workspace_inside(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("WCF-0042"))

    session_dir = tmp_path / "sessions" / "dev-tkt-store-wcf-0042"
    assert opened.created
    assert opened.dir == session_dir
    assert opened.definition == SandboxDefinition.read(session_dir)
    assert opened.definition.name == "dev-tkt-store-wcf-0042"
    assert opened.definition.workspace_dir == session_dir / "workspace"
    assert opened.definition.workspace_dir.is_dir()
    assert opened.definition.agent_kit_dir == tmp_path / "agent-kit"
    assert sorted(path.name for path in session_dir.iterdir()) == ["sbxenv.yaml", "workspace"]


def test_the_definition_carries_the_variables_the_agent_kit_reads(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("WCF-0042"))

    assert opened.definition.variables == {
        "AGENT_ROLE": "dev",
        "AGENT_TASK": "wcf-0042",
        "AGENT_KIT_DIR": str(tmp_path / "agent-kit"),
        "AGENT_REPO_URL": "git@github.com:o/tkt-store.git",
        "AGENT_PROJECT_DIR": "/home/agent/work/tkt-store",
        "AGENT_NOTES_DIR": "/home/agent/work/tkt-store-notes",
        "AGENT_TASK_BRANCH": "task/wcf-0042",
        "AGENT_NOTES_BRANCH": "agent-notes",
        "AGENT_NOTES_ROOT": ".agent",
        "AGENT_TASK_NOTES": ".agent/wcf-0042",
        "AGENT_TASK_FILE": ".agent/wcf-0042/TASK.md",
    }


def test_sandbox_names_are_sbx_safe(tmp_path: Path) -> None:
    project = Project(name="Tkt Store!", url="git@github.com:o/tkt-store.git")
    opened = session.open_or_create(tmp_path, project=project, role=DEV, task=Task("T1"))
    assert opened.dir.name == "dev-tkt-store-t1"


def test_a_sandbox_name_over_the_limit_is_refused(tmp_path: Path) -> None:
    project = Project(name="p" * 60, url="git@github.com:o/p.git")
    with pytest.raises(FoundryError, match="over 64 characters"):
        session.open_or_create(tmp_path, project=project, role=DEV, task=Task("wcf-0042"))
    assert not (tmp_path / "sessions").exists()


def test_a_reopen_reuses_the_definition_unchanged(tmp_path: Path) -> None:
    first = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("WCF-0042"))
    definition_path = first.dir / SandboxDefinition.FILE_NAME
    before = definition_path.read_text()

    second = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("WCF-0042"))

    assert not second.created
    assert (second.dir, second.definition) == (first.dir, first.definition)
    assert definition_path.read_text() == before


@pytest.mark.parametrize(
    ("project", "role", "task"),
    [
        # Slugs collide: dev on foundry, task test-1, and dev on foundry-test, task 1.
        (Project(name="foundry-test", url="git@github.com:o/foundry-test.git"), DEV, Task("1")),
        # The project's url changed since the session was created.
        (Project(name="foundry", url="git@github.com:o/moved.git"), DEV, Task("test-1")),
    ],
)
def test_a_sandbox_for_another_role_task_or_repository_is_refused(
    tmp_path: Path, project: Project, role: Role, task: Task
) -> None:
    foundry = Project(name="foundry", url="git@github.com:o/foundry.git")
    session.open_or_create(tmp_path, project=foundry, role=DEV, task=Task("test-1"))

    with pytest.raises(FoundryError, match="already exists for a different role, task or repository"):
        session.open_or_create(tmp_path, project=project, role=role, task=task)


def test_the_init_command_runs_the_agent_kit_the_sandbox_was_created_with(tmp_path: Path) -> None:
    session.open_or_create(tmp_path / "before", project=TKT_STORE, role=DEV, task=Task("t1"))
    (tmp_path / "before").rename(tmp_path / "after")  # the foundry is moved

    opened = session.open_or_create(tmp_path / "after", project=TKT_STORE, role=DEV, task=Task("t1"))

    assert opened.init_command == (str(tmp_path / "before" / "agent-kit" / "bin" / "session-init"),)


def test_a_session_left_without_its_definition_is_finished(tmp_path: Path) -> None:
    (tmp_path / "sessions" / "dev-tkt-store-wcf-0042" / "workspace").mkdir(parents=True)

    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("WCF-0042"))

    assert opened.created
    assert opened.definition == SandboxDefinition.read(opened.dir)


@pytest.mark.parametrize("leftover", ["workspace/notes.txt", "notes.txt"])
def test_a_session_left_without_its_definition_but_holding_files_is_refused(tmp_path: Path, leftover: str) -> None:
    session_dir = tmp_path / "sessions" / "dev-tkt-store-wcf-0042"
    (session_dir / "workspace").mkdir(parents=True)
    (session_dir / leftover).write_text("x")

    with pytest.raises(FoundryError, match="holds more than an empty workspace"):
        session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("WCF-0042"))
    assert not (session_dir / SandboxDefinition.FILE_NAME).exists()
