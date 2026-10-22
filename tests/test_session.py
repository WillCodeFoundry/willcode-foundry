from datetime import UTC, datetime
from pathlib import Path

import pytest

from foundry import session, yaml_io
from foundry.agent_sandbox import SandboxDefinition, definition
from foundry.errors import FoundryError


def test_sandbox_name_is_stable_and_sbx_safe() -> None:
    assert session.sandbox_name("dev", "tkt-store", "WCF-0042") == "dev-tkt-store-wcf-0042"
    assert session.sandbox_name("dev", "Tkt Store!", "T 1") == "dev-tkt-store-t-1"


def test_sandbox_name_refuses_to_exceed_the_limit() -> None:
    with pytest.raises(FoundryError, match="over 64 characters"):
        session.sandbox_name("dev", "p" * 60, "WCF-0042")


def new_sandbox(tmp_path: Path) -> SandboxDefinition:
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
    sandbox = new_sandbox(tmp_path)
    assert (sandbox.name, sandbox.workspace_dir, sandbox.agent_kit_dir) == (
        "dev-p-t1",
        tmp_path / "ws",
        Path("/f/agent-kit"),
    )
    assert sandbox.variables == {
        "AGENT_ROLE": "dev",
        "AGENT_TASK": "T1",
        "AGENT_KIT_DIR": "/f/agent-kit",
        "AGENT_REPO_URL": "git@h:o/p.git",
        "AGENT_PROJECT_DIR": "/home/agent/work/p",
        "AGENT_NOTES_DIR": "/home/agent/work/p-notes",
    }


def test_create_session_writes_both_files_and_refuses_an_existing_dir(tmp_path: Path) -> None:
    session_dir = tmp_path / "s"
    session.create_session(session_dir, new_sandbox(tmp_path), role="dev")
    assert definition.read(session_dir) == new_sandbox(tmp_path)
    assert yaml_io.load(session_dir / session.RECORD_FILE_NAME) == {"role": "dev", "launches": []}
    with pytest.raises(FoundryError, match="already exists"):
        session.create_session(session_dir, new_sandbox(tmp_path))


def test_record_launch_appends_and_keeps_existing_fields(tmp_path: Path) -> None:
    d = tmp_path / "s"
    session.create_session(d, new_sandbox(tmp_path), sandbox="s")
    first = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)
    session.record_launch(d, launched_at=first)
    session.record_launch(d, launched_at=first.replace(hour=19))
    assert yaml_io.load(d / session.RECORD_FILE_NAME) == {
        "sandbox": "s",
        "launches": [
            {"at": "2026-10-21T18:00:00+00:00"},
            {"at": "2026-10-21T19:00:00+00:00"},
        ],
    }


@pytest.mark.parametrize("content", ["[]\n", "sandbox: s\n", "launches: none\n"])
def test_a_record_foundry_did_not_write_fails_with_its_path(tmp_path: Path, content: str) -> None:
    (tmp_path / session.RECORD_FILE_NAME).write_text(content)
    with pytest.raises(FoundryError, match=r"session.yaml: not a session record written by foundry"):
        session.record_launch(tmp_path, launched_at=datetime.now(UTC))


def test_record_launch_needs_a_record(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match="is missing"):
        session.record_launch(tmp_path, launched_at=datetime.now(UTC))


@pytest.mark.parametrize("task_id", ["WCF-0042", "fix-login.2", "t_1", "7"])
def test_valid_task_ids(task_id: str) -> None:
    session.require_valid_task_id(task_id)


@pytest.mark.parametrize("task_id", ["", "-x", ".x", "feat/x", "a b", "a..b", "x.", "x.lock", "ü", "x~1", "x:y"])
def test_task_ids_that_are_not_valid_branch_names_are_refused(task_id: str) -> None:
    with pytest.raises(FoundryError, match="is not valid"):
        session.require_valid_task_id(task_id)


def test_a_sandbox_for_another_role_task_or_repository_is_refused(tmp_path: Path) -> None:
    sandbox = new_sandbox(tmp_path)  # role dev, task T1, repo git@h:o/p.git
    session.require_same_sandbox(sandbox, role_name="dev", task_id="T1", repo_url="git@h:o/p.git")
    for mismatch in ({"task_id": "t1"}, {"role_name": "qa"}, {"repo_url": "git@h:o/q.git"}):
        wanted = {"role_name": "dev", "task_id": "T1", "repo_url": "git@h:o/p.git", **mismatch}
        with pytest.raises(FoundryError, match="already exists for a different role, task or repository"):
            session.require_same_sandbox(sandbox, **wanted)
