"""config/foundry.yaml: its shape through parse, and each role's files through load, under tmp_path."""

from pathlib import Path

import pytest

from foundry import config
from foundry.errors import FoundryError

REPO_ROOT = Path(__file__).parents[1]

CONFIG = """\
name: test
projects:
  tkt-store: {url: "git@github.com:o/tkt-store.git"}
roles:
  dev: {}
"""


def give_kit_roles(foundry_root: Path, *role_names: str) -> Path:
    """Folders in the foundry's agent kit for these roles, with the files a role must have."""
    for role_name in role_names:
        role_dir = foundry_root / "agent-kit" / "roles" / role_name
        role_dir.mkdir(parents=True)
        for name in ("ROLE.md", "gitconfig"):
            (role_dir / name).write_text("")
    return foundry_root


@pytest.fixture
def foundry_root(tmp_path: Path) -> Path:
    """A foundry listing one project and the dev role, which its agent kit has."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    return give_kit_roles(tmp_path, "dev")


def test_parse_minimal(tmp_path: Path) -> None:
    give_kit_roles(tmp_path, "dev", "qa")
    cfg = config.parse(
        {"name": "x", "projects": {"p": {"url": "git@h:o/p.git"}}, "roles": {"dev": {}, "qa": None}},
        foundry_root=tmp_path,
    )
    assert cfg.project("p").url == "git@h:o/p.git"
    assert cfg.role("dev").name == "dev"
    assert cfg.role("qa").name == "qa"


def test_unknown_project_and_role_are_reported(tmp_path: Path) -> None:
    give_kit_roles(tmp_path, "dev")
    cfg = config.parse({"name": "x", "projects": {}, "roles": {"dev": {}}}, foundry_root=tmp_path)
    with pytest.raises(FoundryError, match="unknown project 'p'"):
        cfg.project("p")
    with pytest.raises(FoundryError, match="unknown role 'qa'; known: dev"):
        cfg.role("qa")


def test_a_role_without_a_model_runs_on_the_default(tmp_path: Path) -> None:
    give_kit_roles(tmp_path, "dev", "qa", "reviewer")
    cfg = config.parse(
        {"name": "x", "roles": {"dev": {}, "qa": None, "reviewer": {"model": None}}}, foundry_root=tmp_path
    )
    assert [role.model for role in cfg.roles.values()] == [None, None, None]


@pytest.mark.parametrize("model", ["opus", "sonnet[1m]", "claude-opus-5-5", "claude-haiku-5-5"])
def test_a_role_s_model_is_read_as_written(tmp_path: Path, model: str) -> None:
    give_kit_roles(tmp_path, "dev")
    cfg = config.parse({"name": "x", "roles": {"dev": {"model": model}}}, foundry_root=tmp_path)
    assert cfg.role("dev").model == model


def test_role_options_other_than_model_are_rejected_not_ignored(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match=r"roles.dev: unknown role option 'memory'; the only one is 'model'"):
        config.parse({"name": "x", "roles": {"dev": {"memory": "8g"}}}, foundry_root=tmp_path)


@pytest.mark.parametrize("model", ["", "--dangerously-skip-permissions", "opus 4", 5, ["opus"]])
def test_a_model_claude_code_couldn_t_take_is_refused(tmp_path: Path, model: object) -> None:
    """A model starting with '-' would be read as another option of Claude Code's."""
    with pytest.raises(FoundryError, match=r"roles.dev.model .* is not a model"):
        config.parse({"name": "x", "roles": {"dev": {"model": model}}}, foundry_root=tmp_path)


def test_role_options_must_be_a_mapping(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match=r"roles.dev must be a mapping"):
        config.parse({"name": "x", "roles": {"dev": "opus"}}, foundry_root=tmp_path)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ([], "^config: top level must be a mapping$"),
        ("x", "^config: top level must be a mapping$"),
        ({}, "^config: 'name' is required$"),
        ({"name": ""}, "^config: 'name' is required$"),
        ({"name": "x", "projects": {"p": {}}}, "^config: projects.p needs a 'url'$"),
    ],
)
def test_invalid_shapes(tmp_path: Path, raw: object, message: str) -> None:
    with pytest.raises(FoundryError, match=message):
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


# --- a role's folder in the agent kit ----------------------------------------------


def test_a_role_without_a_folder_in_the_agent_kit_is_refused(foundry_root: Path) -> None:
    config_path = foundry_root / "config" / "foundry.yaml"
    config_path.write_text(CONFIG + "  tester: {}\n")

    with pytest.raises(
        FoundryError, match=r"role 'tester' has no folder in the agent kit: .*roles/tester doesn't exist"
    ):
        config.load(foundry_root)


@pytest.mark.parametrize("missing", [["ROLE.md"], ["gitconfig"], ["ROLE.md", "gitconfig"]])
def test_a_role_folder_without_what_a_sandbox_needs_is_refused_naming_it(
    foundry_root: Path, missing: list[str]
) -> None:
    for name in missing:
        (foundry_root / "agent-kit" / "roles" / "dev" / name).unlink()

    with pytest.raises(FoundryError, match=rf"role 'dev': .*roles/dev has no {' or '.join(missing)}$"):
        config.load(foundry_root)


def test_a_role_needs_no_skills_folder(foundry_root: Path) -> None:
    assert not (foundry_root / "agent-kit" / "roles" / "dev" / "skills").exists()

    assert config.load(foundry_root).role("dev").name == "dev"


def test_this_foundrys_roles_are_all_in_its_agent_kit() -> None:
    """A role added to config/foundry.yaml without its folder in agent-kit/roles/ fails here, not in a sandbox."""
    assert config.load(REPO_ROOT).roles
