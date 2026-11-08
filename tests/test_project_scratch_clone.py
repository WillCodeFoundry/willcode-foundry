"""ProjectScratchClone, where ProjectTasks can't reach it, against real repositories on disk."""

from pathlib import Path

import pytest

from agent_runtime.git import GitError
from foundry import task
from foundry.errors import FoundryError
from foundry.project_scratch_clone import BranchNotFoundError, PathNotOnBranchError, ProjectScratchClone
from tests.support.project_repository import clone_in, git_output

# --- ProjectScratchClone: what ProjectTasks can't reach ----------------------------------------


def test_a_push_of_no_branches_is_refused(tmp_path: Path, git_env) -> None:
    clone = clone_in(tmp_path, git_env, str(tmp_path / "origin.git"))
    with pytest.raises(ValueError, match="at least one branch"):
        clone.push_atomic(from_remote={}, from_local=[])


def test_move_dir_refuses_an_existing_destination(tmp_path: Path, git_env) -> None:
    clone = clone_in(tmp_path, git_env, str(tmp_path / "origin.git"))
    clone.write({"a/one.md": "1\n", "b/two.md": "2\n"})

    with pytest.raises(FileExistsError):
        clone.move_dir("a", "b")


def test_write_refuses_a_link_and_writes_nothing_through_it(tmp_path: Path, git_env) -> None:
    work_dir = tmp_path / "clone"
    work_dir.mkdir()
    clone = ProjectScratchClone.init(str(tmp_path / "origin.git"), work_dir, git_env)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n")
    (work_dir / "link.md").symlink_to(outside)

    with pytest.raises(FoundryError, match=r"^link\.md is a link: foundry writes only files$"):
        clone.write({"link.md": "2\n"})
    assert outside.read_text() == "outside\n"


# --- ProjectScratchClone.fetch_branch, FetchedBranch: subdir_names, read_text -------------------


def test_fetch_branch_refuses_a_branch_the_remote_lacks(project_repository) -> None:
    clone = project_repository.clone()
    with pytest.raises(BranchNotFoundError, match=r"^the project repository has no nope branch$"):
        clone.fetch_branch("nope")


def test_subdir_names_lists_only_the_dirs_on_a_fetched_branch(project_repository) -> None:
    clone = project_repository.clone()
    notes_branch = clone.fetch_branch(task.NOTES_BRANCH)
    assert notes_branch.subdir_names(task.OPEN_DIR) == ["tst-0000"]
    assert notes_branch.subdir_names(f"{task.OPEN_DIR}/tst-0000") == []  # TASK.md is a file


def test_subdir_names_of_a_missing_dir_raises_the_narrow_error(project_repository) -> None:
    clone = project_repository.clone()
    notes_branch = clone.fetch_branch(task.NOTES_BRANCH)
    with pytest.raises(PathNotOnBranchError):
        notes_branch.subdir_names(".agent/tasks/nope")
    with pytest.raises(PathNotOnBranchError):  # a file is not a dir
        notes_branch.subdir_names(f"{task.OPEN_DIR}/tst-0000/TASK.md")
    with pytest.raises(PathNotOnBranchError):  # a prefix of a dir's name is not that dir
        notes_branch.subdir_names(task.OPEN_DIR[:-1])


def test_read_text_reads_a_file_and_a_link_as_its_target_name(project_repository) -> None:
    project_repository.edit_notes(symlink={".agent/tasks/open/tst-0000/LINK": "/etc/hostname"})
    clone = project_repository.clone()
    notes_branch = clone.fetch_branch(task.NOTES_BRANCH)

    assert notes_branch.read_text(f"{task.OPEN_DIR}/tst-0000/TASK.md") == "tst-0000\n"
    assert notes_branch.read_text(f"{task.OPEN_DIR}/tst-0000/LINK") == "/etc/hostname"


def test_read_text_of_a_missing_file_or_a_dir_raises_the_narrow_error(project_repository) -> None:
    clone = project_repository.clone()
    notes_branch = clone.fetch_branch(task.NOTES_BRANCH)
    # "dir/" makes ls-tree list the dir's contents: still not a file
    for path in (f"{task.OPEN_DIR}/tst-0000/NOPE", f"{task.OPEN_DIR}/tst-0000", f"{task.OPEN_DIR}/tst-0000/"):
        with pytest.raises(PathNotOnBranchError):
            notes_branch.read_text(path)


def test_reads_use_the_commit_fetched_even_after_a_later_fetch(project_repository) -> None:
    clone = project_repository.clone()
    first = clone.fetch_branch(task.NOTES_BRANCH)
    project_repository.edit_notes(write={".agent/tasks/open/tst-0002/TASK.md": "tst-0002\n"})
    second = clone.fetch_branch(task.NOTES_BRANCH)

    assert first.commit != second.commit
    assert first.subdir_names(task.OPEN_DIR) == ["tst-0000"]
    assert second.subdir_names(task.OPEN_DIR) == ["tst-0000", "tst-0002"]


# --- ProjectScratchClone: check_out, start_orphan ----------------------------------------------


def test_check_out_checks_out_the_commit_fetched_not_a_later_one(project_repository) -> None:
    clone = project_repository.clone()
    notes_branch = clone.fetch_branch(task.NOTES_BRANCH)
    project_repository.edit_notes(write={"later.md": "pushed after the fetch\n"})

    clone.check_out(notes_branch)
    clone.write({"mine.md": "1\n"})
    clone.commit("mine")

    with pytest.raises(GitError, match="rejected"):  # never forced: the later commit is kept
        clone.push_atomic(from_remote={}, from_local=[task.NOTES_BRANCH])


def test_start_orphan_starts_a_branch_with_no_history(tmp_path: Path, git_env) -> None:
    work_dir = tmp_path / "clone"
    work_dir.mkdir()
    clone = ProjectScratchClone.init(str(tmp_path / "origin.git"), work_dir, git_env)

    clone.start_orphan("new")

    assert git_output(git_env, "-C", str(work_dir), "branch", "--show-current") == "new"
    assert git_output(git_env, "-C", str(work_dir), "rev-list", "--all") == ""
