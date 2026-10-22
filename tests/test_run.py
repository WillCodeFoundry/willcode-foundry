"""foundry run, end to end up to the hand-over to agent_sandbox."""

import tempfile
from pathlib import Path

import pytest

from foundry import cli, session, yaml_io
from foundry.agent_sandbox import LaunchRequest, SandboxDefinition

CONFIG = """\
name: test
projects:
  tkt-store: {url: "git@github.com:o/tkt-store.git"}
  foundry: {url: "git@github.com:o/foundry.git"}
  foundry-test: {url: "git@github.com:o/foundry-test.git"}
roles:
  dev: {}
"""


class Launched(Exception):
    def __init__(self, launch: LaunchRequest) -> None:
        self.launch = launch


@pytest.fixture
def instance(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    (tmp_path / "agent-kit").mkdir()
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))  # keep mkdtemp out of /tmp
    monkeypatch.chdir(tmp_path)

    def fake_run(launch: LaunchRequest) -> None:
        raise Launched(launch)

    monkeypatch.setattr("foundry.agent_sandbox.launch", fake_run)
    return tmp_path


def launch(*argv: str) -> LaunchRequest:
    with pytest.raises(Launched) as raised:
        cli.main(["run", *argv])
    return raised.value.launch


def test_first_run_creates_the_session_named_after_the_sandbox(instance: Path) -> None:
    got = launch("tkt-store", "dev", "WCF-0042")

    session_dir = instance / "sessions" / "dev-tkt-store-wcf-0042"
    definition = SandboxDefinition.read(session_dir)
    assert definition.name == "dev-tkt-store-wcf-0042"
    assert got.definition_dir == session_dir
    assert definition.agent_kit_dir == instance / "agent-kit"
    assert got.init_command == (str(instance / "agent-kit" / "bin" / "session-init"),)
    assert got.ssh_key_path == instance / "secrets" / "ssh" / "dev"
    assert got.github_token_path is None
    assert definition.variables["AGENT_TASK"] == "WCF-0042"
    assert definition.workspace_dir.is_dir()


def test_a_rerun_reattaches_with_the_same_file_and_records_each_launch(instance: Path) -> None:
    first = launch("tkt-store", "dev", "WCF-0042")
    definition_path = first.definition_dir / SandboxDefinition.FILE_NAME
    before = definition_path.read_text()
    SandboxDefinition.read(first.definition_dir).workspace_dir.rmdir()  # as if /tmp was cleared

    second = launch("tkt-store", "dev", "WCF-0042")

    assert second.definition_dir == first.definition_dir
    assert definition_path.read_text() == before
    assert SandboxDefinition.read(second.definition_dir).workspace_dir.is_dir()
    launches = yaml_io.load(first.definition_dir / session.RECORD_FILE_NAME)["launches"]
    assert len(launches) == 2


def test_a_token_file_is_passed_when_present(instance: Path) -> None:
    token = instance / "secrets" / "github" / "dev.token"
    token.parent.mkdir(parents=True)
    token.write_text("ghp_x")
    assert launch("tkt-store", "dev", "WCF-0042").github_token_path == token


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


def test_a_colliding_sandbox_name_is_refused_not_reattached(instance: Path, capsys) -> None:
    launch("foundry", "dev", "test-1")

    assert cli.main(["run", "foundry-test", "dev", "1"]) == 1  # also dev-foundry-test-1
    assert "already exists for a different role, task or repository" in capsys.readouterr().err


def test_an_invalid_task_id_is_refused_before_anything_is_created(instance: Path, capsys) -> None:
    assert cli.main(["run", "tkt-store", "dev", "feat/x"]) == 1
    assert "task id 'feat/x' is not valid" in capsys.readouterr().err
    assert not (instance / "sessions").exists()
