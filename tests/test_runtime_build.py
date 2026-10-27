"""foundry.runtime_build: the agent runtime built into an agent kit, as its sandboxes run it."""

import os
import stat
import zipfile
from pathlib import Path

import pytest

from agent_runtime.agent_kit import AgentKit
from foundry.errors import FoundryError
from foundry.runtime_build import build_runtime


@pytest.fixture
def kit_dir(tmp_path: Path) -> Path:
    kit = tmp_path / "agent-kit"
    kit.mkdir()
    return kit


def test_the_runtime_is_built_into_the_kit_with_its_entry_point(kit_dir: Path) -> None:
    built = build_runtime(kit_dir)

    assert built == AgentKit(kit_dir).runtime == kit_dir / ".build" / "agent_runtime.pyz"
    names = zipfile.ZipFile(built).namelist()
    assert "__main__.py" in names and "agent_runtime/contract.py" in names
    assert all(name == "__main__.py" or name.startswith("agent_runtime/") for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)


def test_the_sandboxs_user_can_read_it(kit_dir: Path) -> None:
    assert stat.S_IMODE(build_runtime(kit_dir).stat().st_mode) == 0o644


def test_building_again_succeeds_and_leaves_nothing_behind(kit_dir: Path) -> None:
    first = zipfile.ZipFile(build_runtime(kit_dir)).namelist()

    second = build_runtime(kit_dir)

    assert sorted(zipfile.ZipFile(second).namelist()) == sorted(first)
    assert sorted(path.name for path in second.parent.iterdir()) == ["agent_runtime.pyz"]


def test_a_rebuild_replaces_the_file_whole(kit_dir: Path) -> None:
    """A reader holding the old file keeps reading all of it: the new one is renamed over it, not rewritten."""
    built = build_runtime(kit_dir)
    with built.open("rb") as old:
        old_inode = os.fstat(old.fileno()).st_ino
        build_runtime(kit_dir)
        assert built.stat().st_ino != old_inode
        assert zipfile.ZipFile(old).testzip() is None


def test_a_missing_kit_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match=r"agent kit .* is missing"):
        build_runtime(tmp_path / "nowhere")


def test_a_kit_that_cant_be_written_is_reported(kit_dir: Path) -> None:
    (kit_dir / ".build").write_text("a file where the folder goes\n")

    with pytest.raises(FoundryError, match="can't build the agent runtime"):
        build_runtime(kit_dir)
