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


def test_find_foundry_root_fails_outside_a_foundry(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match="not inside a foundry:"):
        paths.find_foundry_root(tmp_path)
