"""ProjectClone, where ProjectTasks can't reach it, against real repositories on disk."""

from pathlib import Path

import pytest

from foundry import task
from foundry.errors import FoundryError
from foundry.project_clone import NotOnBranchError, ProjectClone
from tests.support.project_repository import clone_in

# --- ProjectClone: what ProjectTasks can't reach ----------------------------------------


def test_a_push_of_no_branches_is_refused(tmp_path: Path, git_env) -> None:
    clone = clone_in(tmp_path, git_env, str(tmp_path / "origin.git"))
    with pytest.raises(AssertionError, match="at least one branch"):
        clone.push_atomic(from_remote={}, from_local=[])


def test_move_dir_refuses_an_existing_destination(tmp_path: Path, git_env) -> None:
    clone = clone_in(tmp_path, git_env, str(tmp_path / "origin.git"))
    clone.write({"a/one.md": "1\n", "b/two.md": "2\n"})

    with pytest.raises(FileExistsError):
        clone.move_dir("a", "b")


def test_write_refuses_a_link_and_writes_nothing_through_it(tmp_path: Path, git_env) -> None:
    work_dir = tmp_path / "clone"
    work_dir.mkdir()
    clone = ProjectClone.init(str(tmp_path / "origin.git"), work_dir, git_env)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n")
    (work_dir / "link.md").symlink_to(outside)

    with pytest.raises(FoundryError, match=r"^link\.md is a link: foundry writes only files$"):
        clone.write({"link.md": "2\n"})
    assert outside.read_text() == "outside\n"


# --- ProjectClone: fetch_branch, fetched_list_dir, fetched_read -------------------------


def test_fetch_branch_refuses_a_branch_the_remote_lacks(project_repository) -> None:
    clone = project_repository.clone()
    with pytest.raises(FoundryError, match=r"^the repository has no nope branch$"):
        clone.fetch_branch("nope")


def test_fetched_list_dir_lists_only_the_directories_in_a_fetched_branch(project_repository) -> None:
    clone = project_repository.fetched_clone()
    assert clone.fetched_list_dir(task.NOTES_BRANCH, task.OPEN_DIR) == ["tst-0000"]
    assert clone.fetched_list_dir(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000") == []  # TASK.md is a file


def test_fetched_list_dir_of_a_missing_dir_raises_the_narrow_error(project_repository) -> None:
    clone = project_repository.fetched_clone()
    with pytest.raises(NotOnBranchError):
        clone.fetched_list_dir(task.NOTES_BRANCH, ".agent/tasks/nope")
    with pytest.raises(NotOnBranchError):  # a file is not a dir
        clone.fetched_list_dir(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000/TASK.md")
    with pytest.raises(NotOnBranchError):  # a prefix of a dir's name is not that dir
        clone.fetched_list_dir(task.NOTES_BRANCH, task.OPEN_DIR[:-1])


def test_fetched_reads_of_an_unfetched_branch_raise_something_broader(project_repository) -> None:
    clone = project_repository.clone()
    for call in (
        lambda: clone.fetched_list_dir(task.NOTES_BRANCH, task.OPEN_DIR),
        lambda: clone.fetched_read(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000/TASK.md"),
    ):
        with pytest.raises(FoundryError, match=r"agent-notes isn't fetched") as raised:
            call()
        assert not isinstance(raised.value, NotOnBranchError)


def test_fetched_read_reads_a_file_and_a_link_as_its_target_name(project_repository) -> None:
    project_repository.edit_notes(symlink={".agent/tasks/open/tst-0000/LINK": "/etc/hostname"})

    clone = project_repository.fetched_clone()

    assert clone.fetched_read(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000/TASK.md") == "tst-0000\n"
    assert clone.fetched_read(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000/LINK") == "/etc/hostname"


def test_fetched_read_of_a_missing_file_or_a_dir_raises_the_narrow_error(project_repository) -> None:
    clone = project_repository.fetched_clone()
    # "dir/" makes ls-tree list the dir's contents: still not a file
    for path in (f"{task.OPEN_DIR}/tst-0000/NOPE", f"{task.OPEN_DIR}/tst-0000", f"{task.OPEN_DIR}/tst-0000/"):
        with pytest.raises(NotOnBranchError):
            clone.fetched_read(task.NOTES_BRANCH, path)
