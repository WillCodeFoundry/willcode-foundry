from datetime import datetime
from pathlib import Path

import pytest
import yaml

from foundry import session
from foundry.errors import FoundryError


def test_sandbox_name_is_stable_and_sbx_safe() -> None:
    assert session.sandbox_name("dev", "tkt-store", "WCF-0042") == "dev-tkt-store-wcf-0042"
    assert session.sandbox_name("planner", "Tkt Store!", None) == "planner-tkt-store"


def test_sandbox_name_refuses_to_exceed_the_limit() -> None:
    with pytest.raises(FoundryError, match="over 64 characters"):
        session.sandbox_name("dev", "p" * 60, "WCF-0042")


def test_session_name_is_chronological_to_the_second() -> None:
    assert session.session_name(datetime(2026, 10, 21, 16, 30, 5), "s") == "20261021-163005-s"


def doc(tmp_path: Path, task: str | None = "T1") -> dict:  # type: ignore[type-arg]
    return session.env_document(
        sandbox="dev-p-t1", workspace=tmp_path / "ws", kit_dir=Path("/f/agent-kit"),
        repo_url="git@h:o/p.git", role="dev", task=task, project="p",
    )


def test_env_document(tmp_path: Path) -> None:
    d = doc(tmp_path)
    assert session.workspace_dir(d) == tmp_path / "ws"
    assert session.kit_dir(d) == Path("/f/agent-kit")
    assert d["additionalWorkspaces"] == [{"path": "/f/agent-kit", "readOnly": True}]
    assert d["env"] == {
        "AGENT_ROLE": "dev", "AGENT_TASK": "T1", "AGENT_KIT_DIR": "/f/agent-kit", "AGENT_REPO_URL": "git@h:o/p.git",
        "AGENT_PROJECT_DIR": "/home/agent/work/p", "AGENT_NOTES_DIR": "/home/agent/work/p-notes",
    }


def test_env_document_without_task_has_no_task_var(tmp_path: Path) -> None:
    assert "AGENT_TASK" not in doc(tmp_path, task=None)["env"]


def test_create_session_writes_both_files_and_refuses_an_existing_dir(tmp_path: Path) -> None:
    d = tmp_path / "s"
    session.create_session(d, doc(tmp_path), role="dev", status="created")
    assert session.read_env_file(d)["name"] == "dev-p-t1"
    assert session.read_record(d) == {"role": "dev", "status": "created"}
    with pytest.raises(FoundryError, match="already exists"):
        session.create_session(d, doc(tmp_path))


def test_read_env_file_rejects_the_wrong_shape(tmp_path: Path) -> None:
    (tmp_path / "sbxenv.yaml").write_text("name: x\nenv: {}\n")
    with pytest.raises(FoundryError, match="not a foundry sandbox environment file"):
        session.read_env_file(tmp_path)


def test_update_record_keeps_existing_fields_and_needs_a_record(tmp_path: Path) -> None:
    d = tmp_path / "s"
    session.create_session(d, doc(tmp_path), sandbox="s", status="created")
    session.update_record(d, status="harvested")
    assert yaml.safe_load((d / "session.yaml").read_text()) == {"sandbox": "s", "status": "harvested"}
    with pytest.raises(FoundryError, match="is missing"):
        session.update_record(tmp_path / "other", status="x")
