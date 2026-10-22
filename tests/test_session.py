from datetime import UTC, datetime
from pathlib import Path

import pytest

from foundry import session, yaml_io
from foundry.errors import FoundryError


def test_sandbox_name_is_stable_and_sbx_safe() -> None:
    assert session.sandbox_name("dev", "tkt-store", "WCF-0042") == "dev-tkt-store-wcf-0042"
    assert session.sandbox_name("dev", "Tkt Store!", "T 1") == "dev-tkt-store-t-1"


def test_sandbox_name_refuses_to_exceed_the_limit() -> None:
    with pytest.raises(FoundryError, match="over 64 characters"):
        session.sandbox_name("dev", "p" * 60, "WCF-0042")


def test_sandbox_name_refuses_an_unusable_name() -> None:
    with pytest.raises(FoundryError, match="cannot build a valid sandbox name"):
        session.sandbox_name("!", "!", "!")


def doc(tmp_path: Path) -> session.EnvFile:
    return session.env_document(
        sandbox="dev-p-t1",
        workspace=tmp_path / "ws",
        kit_dir=Path("/f/agent-kit"),
        repo_url="git@h:o/p.git",
        role="dev",
        task="T1",
        project="p",
    )


def test_env_document(tmp_path: Path) -> None:
    d = doc(tmp_path)
    assert session.workspace_dir(d) == tmp_path / "ws"
    assert session.kit_dir(d) == Path("/f/agent-kit")
    assert d["additionalWorkspaces"] == [{"path": "/f/agent-kit", "readOnly": True}]
    assert d["env"] == {
        session.ROLE: "dev",
        session.TASK: "T1",
        session.KIT_DIR: "/f/agent-kit",
        session.REPO_URL: "git@h:o/p.git",
        session.PROJECT_DIR: "/home/agent/work/p",
        session.NOTES_DIR: "/home/agent/work/p-notes",
    }


def test_create_session_writes_both_files_and_refuses_an_existing_dir(tmp_path: Path) -> None:
    d = tmp_path / "s"
    session.create_session(d, doc(tmp_path), role="dev")
    assert session.read_env_file(d)["name"] == "dev-p-t1"
    assert yaml_io.load(d / session.RECORD_FILE) == {"role": "dev", "launches": []}
    with pytest.raises(FoundryError, match="already exists"):
        session.create_session(d, doc(tmp_path))


@pytest.mark.parametrize(
    "content",
    [
        "name: x\nenv: {}\n",
        "[]\n",
        "name: x\nworkspace: /w\nenv: {AGENT_ROLE: dev, AGENT_TASK: t}\nadditionalWorkspaces: []\n",
    ],
)
def test_read_env_file_rejects_the_wrong_shape(tmp_path: Path, content: str) -> None:
    (tmp_path / session.ENV_FILE).write_text(content)
    with pytest.raises(FoundryError, match="not a foundry sandbox environment file"):
        session.read_env_file(tmp_path)


def test_record_launch_appends_and_keeps_existing_fields(tmp_path: Path) -> None:
    d = tmp_path / "s"
    session.create_session(d, doc(tmp_path), sandbox="s")
    first = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)
    session.record_launch(d, at=first, fresh=False)
    session.record_launch(d, at=first.replace(hour=19), fresh=True)
    assert yaml_io.load(d / session.RECORD_FILE) == {
        "sandbox": "s",
        "launches": [
            {"at": "2026-10-21T18:00:00+00:00", "fresh": False},
            {"at": "2026-10-21T19:00:00+00:00", "fresh": True},
        ],
    }


def test_record_launch_needs_a_record(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match="is missing"):
        session.record_launch(tmp_path, at=datetime.now(UTC), fresh=False)
