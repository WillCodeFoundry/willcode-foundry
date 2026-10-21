"""foundry run, end to end up to the hand-over to agent_sandbox."""

import tempfile
from pathlib import Path

import pytest

from foundry import cli, session, yaml_io
from foundry.agent_sandbox import Launch

CONFIG = """\
name: test
projects:
  tkt-store: {url: "git@github.com:o/tkt-store.git"}
roles:
  dev: {}
"""


class Launched(Exception):
    def __init__(self, launch: Launch) -> None:
        self.launch = launch


@pytest.fixture
def instance(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    (tmp_path / "agent-kit").mkdir()
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))  # keep mkdtemp out of /tmp
    monkeypatch.chdir(tmp_path)

    def fake_run(launch: Launch) -> None:
        raise Launched(launch)

    monkeypatch.setattr("foundry.agent_sandbox.run", fake_run)
    return tmp_path


def launch(*argv: str) -> Launch:
    with pytest.raises(Launched) as raised:
        cli.main(["run", *argv])
    return raised.value.launch


def test_first_run_creates_the_session_named_after_the_sandbox(instance: Path) -> None:
    got = launch("tkt-store", "dev", "WCF-0042", "--", "--continue")

    session_dir = instance / "sessions" / "dev-tkt-store-wcf-0042"
    doc = session.read_env_file(session_dir)
    assert got.name == doc["name"] == "dev-tkt-store-wcf-0042"
    assert got.env_dir == session_dir
    assert got.context == instance / "agent-kit"
    assert got.init == (str(instance / "agent-kit" / "bin" / "session-init"),)
    assert got.ssh_key == instance / "secrets" / "ssh" / "dev"
    assert got.github_token_file is None
    assert got.agent_args == ("--continue",)
    assert doc["env"][session.TASK] == "WCF-0042"
    assert session.workspace_dir(doc).is_dir()


def test_a_rerun_reattaches_with_the_same_file_and_records_each_launch(instance: Path) -> None:
    first = launch("tkt-store", "dev", "WCF-0042")
    env_file = first.env_dir / session.ENV_FILE
    before = env_file.read_text()
    session.workspace_dir(session.read_env_file(first.env_dir)).rmdir()  # as if /tmp was cleared

    second = launch("tkt-store", "dev", "WCF-0042", "--new")

    assert second.env_dir == first.env_dir and second.fresh
    assert env_file.read_text() == before
    assert session.workspace_dir(session.read_env_file(second.env_dir)).is_dir()
    launches = yaml_io.load(first.env_dir / session.RECORD_FILE)["launches"]
    assert [entry["fresh"] for entry in launches] == [False, True]


def test_a_token_file_is_passed_when_present(instance: Path) -> None:
    token = instance / "secrets" / "github" / "dev.token"
    token.parent.mkdir(parents=True)
    token.write_text("ghp_x")
    assert launch("tkt-store", "dev", "WCF-0042").github_token_file == token


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["nope", "dev", "T1"], "unknown project 'nope'"),
        (["tkt-store", "qa", "T1"], "unknown role 'qa'; known: dev"),
    ],
)
def test_unknown_names_are_reported(instance: Path, capsys, argv: list[str], message: str) -> None:
    assert cli.main(["run", *argv]) == 1
    assert message in capsys.readouterr().err


def test_the_task_is_required(instance: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["run", "tkt-store", "dev"])
