from pathlib import Path

import pytest

from foundry import paths
from foundry.errors import FoundryError


def test_find_foundry_root_walks_up(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text("name: t\n")
    deep = tmp_path / "sessions" / "x"
    deep.mkdir(parents=True)
    assert paths.find_foundry_root(deep) == tmp_path


def test_find_foundry_root_fails_outside_an_instance(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match="not inside a foundry instance"):
        paths.find_foundry_root(tmp_path)


def test_paths_are_built_without_touching_the_filesystem(tmp_path: Path) -> None:
    assert paths.agent_kit_dir(tmp_path) == tmp_path / "agent-kit"
    assert paths.lifecycle_path(tmp_path, "feature") == tmp_path / "agent-kit" / "lifecycle" / "feature.json"
    assert paths.role_dir(tmp_path, "dev") == tmp_path / "agent-kit" / "roles" / "dev"
    assert paths.ssh_key_path(tmp_path, "dev") == tmp_path / "secrets" / "ssh" / "dev"
    assert paths.github_token_path(tmp_path, "dev") == tmp_path / "secrets" / "github" / "dev.token"
    assert paths.session_dir(tmp_path, "s") == tmp_path / "sessions" / "s"
