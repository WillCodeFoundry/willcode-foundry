from pathlib import Path

import pytest

from foundry import yaml_io
from foundry.errors import FoundryError


def test_round_trip_and_no_temp_file_left(tmp_path: Path) -> None:
    path = tmp_path / "f.yaml"
    yaml_io.dump(path, {"b": 1, "a": [2]})
    assert yaml_io.load(path) == {"b": 1, "a": [2]}
    assert [p.name for p in tmp_path.iterdir()] == ["f.yaml"]


def test_missing_and_invalid_files_are_foundry_errors(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match="is missing"):
        yaml_io.load(tmp_path / "nope.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [unclosed\n")
    with pytest.raises(FoundryError, match="not valid YAML"):
        yaml_io.load(bad)
