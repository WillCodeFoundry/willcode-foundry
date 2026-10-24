from pathlib import Path

import pytest

from foundry import session
from foundry.agent_sandbox import SandboxDefinition
from foundry.errors import FoundryError


def test_sandbox_name_is_stable_and_sbx_safe() -> None:
    assert session.sandbox_name("dev", "tkt-store", "WCF-0042") == "dev-tkt-store-wcf-0042"
    assert session.sandbox_name("dev", "Tkt Store!", "T 1") == "dev-tkt-store-t-1"


def test_sandbox_name_refuses_to_exceed_the_limit() -> None:
    with pytest.raises(FoundryError, match="over 64 characters"):
        session.sandbox_name("dev", "p" * 60, "WCF-0042")


def new_definition(tmp_path: Path) -> SandboxDefinition:
    return session.sandbox_definition(
        sandbox_name="dev-p-t1",
        workspace_dir=tmp_path / "ws",
        agent_kit_dir=Path("/f/agent-kit"),
        repo_url="git@h:o/p.git",
        role_name="dev",
        task_id="T1",
        project_name="p",
    )


def test_sandbox_definition(tmp_path: Path) -> None:
    definition = new_definition(tmp_path)
    assert (definition.name, definition.workspace_dir, definition.agent_kit_dir) == (
        "dev-p-t1",
        tmp_path / "ws",
        Path("/f/agent-kit"),
    )
    assert definition.variables == {
        "AGENT_ROLE": "dev",
        "AGENT_TASK": "T1",
        "AGENT_KIT_DIR": "/f/agent-kit",
        "AGENT_REPO_URL": "git@h:o/p.git",
        "AGENT_PROJECT_DIR": "/home/agent/work/p",
        "AGENT_NOTES_DIR": "/home/agent/work/p-notes",
    }


def test_create_writes_the_definition_and_creates_the_workspace(tmp_path: Path) -> None:
    session_dir = tmp_path / "s"
    definition = session.sandbox_definition(
        sandbox_name="dev-p-t1",
        workspace_dir=session_dir / "workspace",
        agent_kit_dir=Path("/f/agent-kit"),
        repo_url="git@h:o/p.git",
        role_name="dev",
        task_id="T1",
        project_name="p",
    )
    session.create(session_dir, definition)
    assert SandboxDefinition.read(session_dir) == definition
    assert definition.workspace_dir.is_dir()
    assert sorted(path.name for path in session_dir.iterdir()) == ["sbxenv.yaml", "workspace"]


def test_create_refuses_an_existing_directory(tmp_path: Path) -> None:
    (tmp_path / "s").mkdir()
    with pytest.raises(FoundryError, match="already exists"):
        session.create(tmp_path / "s", new_definition(tmp_path))


def test_a_sandbox_for_another_role_task_or_repository_is_refused(tmp_path: Path) -> None:
    definition = new_definition(tmp_path)  # role dev, task T1, repo git@h:o/p.git
    session.require_same_sandbox(definition, role_name="dev", task_id="T1", repo_url="git@h:o/p.git")
    for mismatch in ({"task_id": "t1"}, {"role_name": "qa"}, {"repo_url": "git@h:o/q.git"}):
        wanted = {"role_name": "dev", "task_id": "T1", "repo_url": "git@h:o/p.git", **mismatch}
        with pytest.raises(FoundryError, match="already exists for a different role, task or repository"):
            session.require_same_sandbox(definition, **wanted)
