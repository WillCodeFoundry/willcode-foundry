from pathlib import Path

import pytest

from foundry import yaml_io
from foundry.errors import FoundryError


def test_missing_and_invalid_files_are_foundry_errors(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match="is missing"):
        yaml_io.load(tmp_path / "nope.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [unclosed\n")
    with pytest.raises(FoundryError, match="not valid YAML"):
        yaml_io.load(bad)
