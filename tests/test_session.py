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
    return session.build_env_file(
        sandbox_name="dev-p-t1",
        workspace_path=tmp_path / "ws",
        agent_kit_path=Path("/f/agent-kit"),
        repo_url="git@h:o/p.git",
        role_name="dev",
        task_id="T1",
        project_name="p",
    )


def test_build_env_file(tmp_path: Path) -> None:
    d = doc(tmp_path)
    assert session.workspace_path(d) == tmp_path / "ws"
    assert session.agent_kit_path(d) == Path("/f/agent-kit")
    assert d["additionalWorkspaces"] == [{"path": "/f/agent-kit", "readOnly": True}]
    assert d["env"] == {
        session.AGENT_ROLE_VAR: "dev",
        session.AGENT_TASK_VAR: "T1",
        session.AGENT_KIT_DIR_VAR: "/f/agent-kit",
        session.AGENT_REPO_URL_VAR: "git@h:o/p.git",
        session.AGENT_PROJECT_DIR_VAR: "/home/agent/work/p",
        session.AGENT_NOTES_DIR_VAR: "/home/agent/work/p-notes",
    }


def test_create_session_writes_both_files_and_refuses_an_existing_dir(tmp_path: Path) -> None:
    d = tmp_path / "s"
    session.create_session(d, doc(tmp_path), role="dev")
    assert session.read_env_file(d)["name"] == "dev-p-t1"
    assert yaml_io.load(d / session.RECORD_FILE_NAME) == {"role": "dev", "launches": []}
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
    (tmp_path / session.ENV_FILE_NAME).write_text(content)
    with pytest.raises(FoundryError, match="not a foundry sandbox environment file"):
        session.read_env_file(tmp_path)


def test_record_launch_appends_and_keeps_existing_fields(tmp_path: Path) -> None:
    d = tmp_path / "s"
    session.create_session(d, doc(tmp_path), sandbox="s")
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


def test_record_launch_needs_a_record(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match="is missing"):
        session.record_launch(tmp_path, launched_at=datetime.now(UTC))


@pytest.mark.parametrize("task_id", ["WCF-0042", "fix-login.2", "t_1", "7"])
def test_valid_task_ids(task_id: str) -> None:
    session.ensure_valid_task_id(task_id)


@pytest.mark.parametrize("task_id", ["", "-x", ".x", "feat/x", "a b", "a..b", "x.", "x.lock", "ü", "x~1", "x:y"])
def test_task_ids_that_are_not_valid_branch_names_are_refused(task_id: str) -> None:
    with pytest.raises(FoundryError, match="is not valid"):
        session.ensure_valid_task_id(task_id)


def test_an_env_file_for_another_run_is_refused(tmp_path: Path) -> None:
    env_file = doc(tmp_path)  # role dev, task T1, repo git@h:o/p.git
    session.ensure_env_file_matches(env_file, role_name="dev", task_id="T1", repo_url="git@h:o/p.git")
    for mismatch in ({"task_id": "t1"}, {"role_name": "qa"}, {"repo_url": "git@h:o/q.git"}):
        wanted = {"role_name": "dev", "task_id": "T1", "repo_url": "git@h:o/p.git", **mismatch}
        with pytest.raises(FoundryError, match="already exists for a different run"):
            session.ensure_env_file_matches(env_file, **wanted)
