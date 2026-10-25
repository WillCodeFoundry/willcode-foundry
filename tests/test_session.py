"""Sessions, through open_or_create against a foundry root under tmp_path; and SessionVariables."""

import dataclasses
from pathlib import Path

import pytest

from foundry import session
from foundry.agent_sandbox import SandboxDefinition
from foundry.config import Project, Role
from foundry.errors import FoundryError
from foundry.session import SessionVariables
from foundry.task import Task

TKT_STORE = Project(name="tkt-store", url="git@github.com:o/tkt-store.git")
DEV = Role(name="dev", ssh_key_path=Path("/foundry/secrets/ssh/dev"), github_token_path=None)


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
    assert opened.variables.agent_kit_dir == tmp_path / "before" / "agent-kit"  # what the sandbox was told


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


# --- session variables ---------------------------------------------------------


def test_the_session_carries_its_variables(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("WCF-0042"))

    assert opened.variables == SessionVariables(
        role_name="dev",
        task=Task("wcf-0042"),
        repo_url="git@github.com:o/tkt-store.git",
        agent_kit_dir=tmp_path / "agent-kit",
        project_dir="/home/agent/work/tkt-store",
    )
    assert opened.variables.as_env() == opened.definition.variables


def test_variables_read_back_are_the_variables_written(tmp_path: Path) -> None:
    variables = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("t1")).variables

    assert SessionVariables.from_env(variables.as_env()) == variables


def rewrite_variables(session_dir: Path, change: dict[str, str | None]) -> None:
    """Rewrite a session's definition with some variables changed, or removed where None: an older foundry's."""
    definition = SandboxDefinition.read(session_dir)
    variables = {**definition.variables, **change}
    kept = {name: value for name, value in variables.items() if value is not None}
    dataclasses.replace(definition, variables=kept).write(session_dir)


def test_a_sandbox_created_without_a_variable_is_refused_naming_it(tmp_path: Path) -> None:
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("t1"))
    rewrite_variables(opened.dir, {"AGENT_TASK_FILE": None, "AGENT_NOTES_ROOT": None})

    with pytest.raises(FoundryError, match=r"missing AGENT_NOTES_ROOT, AGENT_TASK_FILE\).*sbx env rm --force"):
        session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("t1"))


def test_a_sandbox_created_with_another_name_is_refused_naming_both(tmp_path: Path) -> None:
    """Its hooks would guard the old branch, so it is recreated rather than reused."""
    opened = session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("t1"))
    rewrite_variables(opened.dir, {"AGENT_NOTES_BRANCH": "notes"})

    with pytest.raises(FoundryError, match="AGENT_NOTES_BRANCH='notes', now 'agent-notes'"):
        session.open_or_create(tmp_path, project=TKT_STORE, role=DEV, task=Task("t1"))


def test_the_same_sandbox_is_the_same_role_task_and_repository_whatever_the_paths() -> None:
    variables = SessionVariables(
        role_name="dev", task=Task("t1"), repo_url="u", agent_kit_dir=Path("/kit"), project_dir="/w/p"
    )

    assert variables.is_same_sandbox(dataclasses.replace(variables, agent_kit_dir=Path("/moved"), project_dir="/w/q"))
    for other in (
        dataclasses.replace(variables, role_name="qa"),
        dataclasses.replace(variables, task=Task("t2")),
        dataclasses.replace(variables, repo_url="v"),
    ):
        assert not variables.is_same_sandbox(other)
