"""foundry.runtime_build: the agent runtime built into an agent kit, as its sandboxes run it."""

import os
import stat
import zipfile
from pathlib import Path

import pytest

import agent_runtime
from agent_runtime.agent_kit import AgentKit
from foundry.errors import FoundryError
from foundry.runtime_build import build_runtime


@pytest.fixture
def kit_dir(tmp_path: Path) -> Path:
    kit = tmp_path / "agent-kit"
    kit.mkdir()
    return kit


def files_in(archive: Path) -> list[str]:
    """The archive's files, without the entries for its folders."""
    return [name for name in zipfile.ZipFile(archive).namelist() if not name.endswith("/")]


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


def test_a_rebuild_of_changed_source_replaces_the_file_whole(kit_dir: Path, tmp_path: Path) -> None:
    """A reader holding the old file keeps reading all of it: the new one is renamed over it, not rewritten."""
    source = tmp_path / "source"
    (source).mkdir()
    (source / "__main__.py").write_text("def main() -> None: ...\n")
    built = build_runtime(kit_dir, source=source)
    (source / "added.py").write_text("")
    with built.open("rb") as old:
        old_inode = os.fstat(old.fileno()).st_ino
        build_runtime(kit_dir, source=source)
        assert built.stat().st_ino != old_inode
        assert zipfile.ZipFile(old).testzip() is None


def test_a_rebuild_of_unchanged_source_leaves_the_file_alone(kit_dir: Path) -> None:
    """A launch rebuilds every time: when nothing changed, a sandbox starting meanwhile keeps the same file."""
    inode = build_runtime(kit_dir).stat().st_ino

    assert build_runtime(kit_dir).stat().st_ino == inode


def test_the_same_files_build_the_same_bytes_whatever_order_and_time_they_were_written_in(tmp_path: Path) -> None:
    """Otherwise a rebuild of unchanged source replaces the file under a sandbox that is starting. CI saw it once
    on Python 3.11, whose zipapp adds files in the order the file system lists them, with their times."""
    built = []
    for name, order, written_at in (
        ("first", ("a.py", "b.py", "__main__.py"), 1_600_000_000),
        ("second", ("__main__.py", "b.py", "a.py"), 1_700_000_000),
    ):
        source, kit = tmp_path / f"source-{name}", tmp_path / f"kit-{name}"
        source.mkdir()
        kit.mkdir()
        for file in order:
            (source / file).write_text(f"# {file}\n")
            os.utime(source / file, (written_at, written_at))
        built.append(build_runtime(kit, source=source).read_bytes())

    assert built[0] == built[1]


def test_every_python_file_of_the_package_is_built_in_its_folders_too(kit_dir: Path, tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "sub" / "__pycache__").mkdir(parents=True)
    for name in (
        "__main__.py",
        "sub/__init__.py",
        "sub/module.py",
        "sub/__pycache__/module.cpython-311.pyc",
        "notes.txt",
    ):
        (source / name).write_text("")

    built = build_runtime(kit_dir, source=source)

    assert sorted(files_in(built)) == [
        "__main__.py",
        "agent_runtime/__main__.py",
        "agent_runtime/sub/__init__.py",
        "agent_runtime/sub/module.py",
    ]


def test_the_real_package_is_built_whole(kit_dir: Path) -> None:
    source = Path(agent_runtime.__file__).parent
    expected = {f"agent_runtime/{path.relative_to(source)}" for path in source.rglob("*.py")}

    assert set(files_in(build_runtime(kit_dir))) - {"__main__.py"} == expected


def test_a_missing_kit_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match=r"agent kit .* is missing"):
        build_runtime(tmp_path / "nowhere")


def test_a_kit_that_cant_be_written_is_reported(kit_dir: Path) -> None:
    (kit_dir / ".build").write_text("a file where the folder goes\n")

    with pytest.raises(FoundryError, match="can't build the agent runtime"):
        build_runtime(kit_dir)
