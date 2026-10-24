"""foundry run, up to the hand-over to agent_sandbox: prepare_launch against a foundry under tmp_path."""

from pathlib import Path

import pytest

from foundry.agent_sandbox import SandboxDefinition
from foundry.commands.run import prepare_launch
from foundry.errors import FoundryError
from foundry.task import Task

CONFIG = """\
name: test
signing_key: ssh-ed25519 AAAATESTKEY
projects:
  tkt-store: {url: "git@github.com:o/tkt-store.git"}
  foundry: {url: "git@github.com:o/foundry.git"}
  foundry-test: {url: "git@github.com:o/foundry-test.git"}
roles:
  dev: {}
"""


@pytest.fixture
def foundry_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    (tmp_path / "agent-kit").mkdir()
    return tmp_path


def test_the_first_launch_creates_the_session_with_its_workspace_inside(foundry_root: Path) -> None:
    request = prepare_launch(foundry_root, "tkt-store", "dev", Task("WCF-0042"))

    session_dir = foundry_root / "sessions" / "dev-tkt-store-wcf-0042"
    definition = SandboxDefinition.read(session_dir)
    assert request.definition_dir == session_dir
    assert definition.name == "dev-tkt-store-wcf-0042"
    assert definition.workspace_dir == session_dir / "workspace"
    assert definition.workspace_dir.is_dir()
    assert definition.agent_kit_dir == foundry_root / "agent-kit"
    assert definition.variables["AGENT_TASK"] == "wcf-0042"
    assert request.init_command == (str(foundry_root / "agent-kit" / "bin" / "session-init"),)
    assert request.ssh_key_path == foundry_root / "secrets" / "ssh" / "dev"
    assert request.github_token_path is None
    assert sorted(path.name for path in session_dir.iterdir()) == ["sbxenv.yaml", "workspace"]  # no session.yaml


def test_a_rerun_reuses_the_definition_unchanged(foundry_root: Path) -> None:
    first = prepare_launch(foundry_root, "tkt-store", "dev", Task("WCF-0042"))
    definition_path = first.definition_dir / SandboxDefinition.FILE_NAME
    before = definition_path.read_text()

    second = prepare_launch(foundry_root, "tkt-store", "dev", Task("WCF-0042"))

    assert second == first
    assert definition_path.read_text() == before


def test_a_token_file_is_passed_when_present(foundry_root: Path) -> None:
    token = foundry_root / "secrets" / "github" / "dev.token"
    token.parent.mkdir(parents=True)
    token.write_text("ghp_x")
    assert prepare_launch(foundry_root, "tkt-store", "dev", Task("WCF-0042")).github_token_path == token


def test_a_colliding_sandbox_name_is_refused_not_reattached(foundry_root: Path) -> None:
    prepare_launch(foundry_root, "foundry", "dev", Task("test-1"))

    with pytest.raises(FoundryError, match="already exists for a different role, task or repository"):
        prepare_launch(foundry_root, "foundry-test", "dev", Task("1"))  # also dev-foundry-test-1


@pytest.mark.parametrize(
    ("project_name", "role_name", "message"),
    [("nope", "dev", "unknown project 'nope'"), ("tkt-store", "qa", "unknown role 'qa'; known: dev")],
)
def test_unknown_names_are_reported(foundry_root: Path, project_name: str, role_name: str, message: str) -> None:
    with pytest.raises(FoundryError, match=message):
        prepare_launch(foundry_root, project_name, role_name, Task("t1"))
