"""agent_runtime.atomic_files: writing beside a file and renaming over it."""

import os
import stat
from pathlib import Path

import pytest

from agent_runtime.atomic_files import atomic_symlink, atomic_write


def test_a_file_is_written_whole_with_its_mode(tmp_path: Path) -> None:
    target = tmp_path / "f"

    atomic_write(target, b"content", mode=0o640)

    assert target.read_bytes() == b"content"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert [path.name for path in tmp_path.iterdir()] == ["f"]


def test_a_reader_of_the_old_file_keeps_it_whole(tmp_path: Path) -> None:
    target = tmp_path / "f"
    target.write_bytes(b"old")
    with target.open("rb") as old:
        atomic_write(target, b"new")
        assert old.read() == b"old"
    assert target.read_bytes() == b"new"


def test_a_link_at_the_target_is_replaced_not_written_through(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_bytes(b"left alone")
    target = tmp_path / "f"
    target.symlink_to(elsewhere)

    atomic_write(target, b"new")

    assert elsewhere.read_bytes() == b"left alone"
    assert not target.is_symlink() and target.read_bytes() == b"new"


def test_links_beside_the_target_are_never_written_through(tmp_path: Path) -> None:
    """The temporary name is fresh each time, so a link someone placed beside the target can't catch the write."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_bytes(b"left alone")
    for name in (".f.partial", ".f.tmp", "f.tmp", ".f.new"):
        (tmp_path / name).symlink_to(elsewhere)

    atomic_write(tmp_path / "f", b"new")

    assert elsewhere.read_bytes() == b"left alone"


def test_a_failed_write_leaves_the_old_file_and_nothing_else(tmp_path: Path) -> None:
    target = tmp_path / "f"
    target.write_bytes(b"old")
    tmp_path.chmod(0o555)
    try:
        with pytest.raises(OSError):
            atomic_write(target, b"new")
    finally:
        tmp_path.chmod(0o755)
    assert target.read_bytes() == b"old"
    assert [path.name for path in tmp_path.iterdir()] == ["f"]


def test_a_link_is_made_or_replaced_in_one_step(tmp_path: Path) -> None:
    link = tmp_path / "link"
    link.write_bytes(b"a file where the link goes")

    atomic_symlink(link, tmp_path / "first")
    atomic_symlink(link, tmp_path / "second")

    assert os.readlink(link) == str(tmp_path / "second")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["link"]
