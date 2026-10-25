"""config/foundry.yaml: its shape through parse, and each role's files through load, under tmp_path."""

from pathlib import Path

import pytest

from foundry import config
from foundry.errors import FoundryError

CONFIG = """\
name: test
projects:
  tkt-store: {url: "git@github.com:o/tkt-store.git"}
roles:
  dev: {}
"""


@pytest.fixture
def foundry_root(tmp_path: Path) -> Path:
    """A foundry listing one project and the dev role."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    return tmp_path


def test_parse_minimal(tmp_path: Path) -> None:
    cfg = config.parse(
        {"name": "x", "projects": {"p": {"url": "git@h:o/p.git"}}, "roles": {"dev": {}, "qa": None}},
        foundry_root=tmp_path,
    )
    assert cfg.project("p").url == "git@h:o/p.git"
    assert cfg.role("dev").name == "dev"
    assert cfg.role("qa").name == "qa"


def test_unknown_project_and_role_are_reported(tmp_path: Path) -> None:
    cfg = config.parse({"name": "x", "projects": {}, "roles": {"dev": {}}}, foundry_root=tmp_path)
    with pytest.raises(FoundryError, match="unknown project 'p'"):
        cfg.project("p")
    with pytest.raises(FoundryError, match="unknown role 'qa'; known: dev"):
        cfg.role("qa")


def test_role_options_are_rejected_not_ignored(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match="role options are not supported yet"):
        config.parse({"name": "x", "roles": {"dev": {"memory": "8g"}}}, foundry_root=tmp_path)


@pytest.mark.parametrize("raw", [[], "x", {}, {"name": ""}, {"name": "x", "projects": {"p": {}}}])
def test_invalid_shapes(tmp_path: Path, raw: object) -> None:
    with pytest.raises(FoundryError):
        config.parse(raw, foundry_root=tmp_path)


# --- a role's files ------------------------------------------------------------------


def test_a_role_has_its_ssh_key_and_no_token_without_a_token_file(foundry_root: Path) -> None:
    role = config.load(foundry_root).role("dev")

    assert role == config.Role(
        name="dev", ssh_key_path=foundry_root / "secrets" / "ssh" / "dev", github_token_path=None
    )


def test_a_role_has_its_token_when_the_token_file_exists(foundry_root: Path) -> None:
    token = foundry_root / "secrets" / "github" / "dev.token"
    token.parent.mkdir(parents=True)
    token.write_text("ghp_x")

    assert config.load(foundry_root).role("dev").github_token_path == token
