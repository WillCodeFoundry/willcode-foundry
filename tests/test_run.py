"""foundry run, up to the hand-over to agent_sandbox: prepare_launch against a foundry under tmp_path."""

import shutil
from pathlib import Path

import pytest

from foundry.agent_sandbox import SandboxDefinition
from foundry.commands.run import prepare_launch
from foundry.errors import FoundryError
from foundry.session import SessionVariables
from foundry.task import Task

CONFIG = """\
name: test
projects:
  tkt-store: {url: "git@github.com:o/tkt-store.git"}
roles:
  dev: {}
"""


@pytest.fixture
def foundry_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    (tmp_path / "agent-kit" / "roles" / "dev").mkdir(parents=True)
    for name in ("ROLE.md", "gitconfig"):
        (tmp_path / "agent-kit" / "roles" / "dev" / name).write_text("")
    return tmp_path


def test_the_first_launch_asks_for_the_new_session_with_the_role_s_key(foundry_root: Path) -> None:
    request = prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task("WCF-0042"))

    session_dir = foundry_root / "sessions" / "dev-tkt-store-wcf-0042"
    assert request.definition_dir == session_dir
    assert SessionVariables.from_env(SandboxDefinition.read(session_dir).variables).task == Task("wcf-0042")
    assert request.init_command == (
        "/usr/bin/python3",
        "-IS",
        str(foundry_root / "agent-kit" / ".build" / "agent_runtime.pyz"),
        "session-init",
    )
    assert request.ssh_key_path == foundry_root / "secrets" / "ssh" / "dev"
    assert request.github_token_path is None


def test_the_runtime_is_built_into_the_kit(foundry_root: Path) -> None:
    prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task("WCF-0042"))

    assert (foundry_root / "agent-kit" / ".build" / "agent_runtime.pyz").is_file()


def test_a_copied_foundry_doesnt_build_into_the_kit_its_sandbox_mounts(foundry_root: Path, tmp_path: Path) -> None:
    """sbx fixed the mount when it created the sandbox, on the original's kit: a copy launching it would swap
    the runtime under the original's sandboxes."""
    prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task("WCF-0042"))
    mounted_pyz = foundry_root / "agent-kit" / ".build" / "agent_runtime.pyz"
    mounted_pyz.unlink()
    copy = tmp_path / "copy"
    shutil.copytree(foundry_root, copy)

    with pytest.raises(FoundryError) as refused:
        prepare_launch(copy, project_name="tkt-store", role_name="dev", task=Task("WCF-0042"))

    assert str(refused.value) == (
        f"dev-tkt-store-wcf-0042 mounts the agent kit at {foundry_root / 'agent-kit'}, not this foundry's "
        f"({copy / 'agent-kit'}): launch it from the foundry there, or recreate it (see Recreating a sandbox in "
        "the README)"
    )
    assert not mounted_pyz.exists()


def test_a_moved_foundry_says_its_sandbox_needs_recreating(foundry_root: Path) -> None:
    """The kit the sandbox mounts is gone with the move: sbx can't mount it again."""
    prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task("WCF-0042"))
    moved = foundry_root.with_name(f"{foundry_root.name}-moved")
    shutil.move(foundry_root, moved)

    with pytest.raises(FoundryError, match=r"mounts the agent kit at .*, which is gone: recreate it \(see"):
        prepare_launch(moved, project_name="tkt-store", role_name="dev", task=Task("WCF-0042"))


def test_a_failed_build_aborts_the_launch(foundry_root: Path) -> None:
    (foundry_root / "agent-kit" / ".build").write_text("a file where the folder goes\n")

    with pytest.raises(FoundryError, match="can't build the agent runtime"):
        prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task("WCF-0042"))


def test_a_rerun_asks_for_the_same_launch(foundry_root: Path) -> None:
    first = prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task("WCF-0042"))
    assert prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task("WCF-0042")) == first


def test_a_token_file_is_passed_when_present(foundry_root: Path) -> None:
    token = foundry_root / "secrets" / "github" / "dev.token"
    token.parent.mkdir(parents=True)
    token.write_text("ghp_x")
    assert (
        prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task("WCF-0042")).github_token_path
        == token
    )


@pytest.mark.parametrize(
    ("project_name", "role_name", "message"),
    [("nope", "dev", "unknown project 'nope'"), ("tkt-store", "qa", "unknown role 'qa'; known: dev")],
)
def test_unknown_names_are_reported(foundry_root: Path, project_name: str, role_name: str, message: str) -> None:
    with pytest.raises(FoundryError, match=message):
        prepare_launch(foundry_root, project_name=project_name, role_name=role_name, task=Task("t1"))
