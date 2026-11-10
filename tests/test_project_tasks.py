"""ProjectTasks against a real repository on disk: creating, finding, closing, reopening and handing off tasks,
and reading and listing their turns."""

import contextlib
from pathlib import Path

import pytest

from agent_runtime.git import GitError
from foundry import task
from foundry.errors import FoundryError
from foundry.project_scratch_clone import BranchNotFoundError, ProjectScratchClone
from foundry.project_tasks import (
    ClosedTaskError,
    MissingTurnError,
    ProjectTasks,
    TaskNotFoundError,
    TaskTurn,
    TaskTurnAndLog,
    last_log_entry,
    log_with_handoff_entry,
)
from foundry.task import Status, Task
from tests.support.machine import counting_stand_in
from tests.support.project_repository import fetch_count, git_output, project_tasks_of

TEMPLATE = {"TASK.md": "# Task <id>: <title>\n", "PROGRESS.md": "# Progress\n"}


def create(project_tasks: ProjectTasks, task_id: str = "tst-0001") -> Task:
    return project_tasks.create_task(task_id, TEMPLATE)


# --- create ---------------------------------------------------------------------


def test_a_task_is_its_branch_from_the_default_branch_and_the_template_in_its_task_notes_dir(
    project_repository,
) -> None:
    notes_before = project_repository.notes_head()

    assert create(project_repository.project_tasks()) == Task.as_open("tst-0001")

    assert project_repository.head("task/tst-0001") == project_repository.head("main")
    assert project_repository.notes_files() == {
        ".agent/tasks/closed/cls-0000/TASK.md": "cls-0000\n",
        ".agent/tasks/open/tst-0000/TASK.md": "tst-0000\n",
        ".agent/tasks/open/tst-0001/PROGRESS.md": "# Progress\n",
        ".agent/tasks/open/tst-0001/TASK.md": "# Task <id>: <title>\n",
    }
    notes_parent = project_repository.git("rev-parse", f"{task.NOTES_BRANCH}^")
    assert notes_parent == notes_before
    assert project_repository.notes_signed_with_your_key()


def test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files(project_repository) -> None:
    project_repository.git("branch", "--quiet", "-D", task.NOTES_BRANCH)

    create(project_repository.project_tasks())

    assert project_repository.notes_files() == {
        ".agent/tasks/open/tst-0001/PROGRESS.md": "# Progress\n",
        ".agent/tasks/open/tst-0001/TASK.md": "# Task <id>: <title>\n",
    }
    assert project_repository.git("rev-list", "--count", task.NOTES_BRANCH) == "1"


def test_without_a_signing_key_nothing_is_pushed(project_repository, no_signing_key) -> None:
    notes_before = project_repository.notes_head()

    with pytest.raises(
        GitError, match=r"(?s)^git -C \S+ commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"
    ):
        create(project_repository.project_tasks())
    assert project_repository.notes_head() == notes_before
    assert "task/tst-0001" not in project_repository.git("branch", "--list")


def test_an_existing_task_branch_is_refused_and_nothing_is_written(project_repository) -> None:
    project_repository.git("branch", "task/tst-0001", "main")
    notes_before = project_repository.notes_head()

    with pytest.raises(FoundryError, match=r"^task tst-0001 already exists: there is a task/tst-0001 branch$"):
        create(project_repository.project_tasks())
    assert project_repository.notes_head() == notes_before


@pytest.mark.parametrize("task_id, found", [("tst-0000", "open/tst-0000"), ("cls-0000", "closed/cls-0000")])
def test_an_existing_task_notes_dir_open_or_closed_is_refused_and_nothing_is_pushed(
    project_repository, task_id: str, found: str
) -> None:
    notes_before = project_repository.notes_head()
    with pytest.raises(FoundryError, match=rf"^task {task_id} already exists: agent-notes has .agent/tasks/{found}/$"):
        create(project_repository.project_tasks(), task_id)
    assert f"task/{task_id}" not in project_repository.git("branch", "--list")
    assert project_repository.notes_head() == notes_before


def test_a_closed_task_that_kept_its_branch_is_refused_naming_its_task_notes_dir(project_repository) -> None:
    project_repository.git("branch", "task/cls-0000", "main")

    with pytest.raises(
        FoundryError, match=r"^task cls-0000 already exists: agent-notes has .agent/tasks/closed/cls-0000/$"
    ):
        create(project_repository.project_tasks(), "cls-0000")


def test_a_repository_with_no_commits_is_refused(tmp_path: Path, git_env) -> None:
    empty_dir = tmp_path / "empty.git"
    git_output(git_env, "init", "--quiet", "--bare", str(empty_dir))

    with pytest.raises(FoundryError, match=r"^the project repository has no commits to branch task/tst-0001 from$"):
        create(project_tasks_of(empty_dir, git_env))


def test_a_default_branch_that_is_not_a_branch_is_refused_and_nothing_is_pushed(project_repository) -> None:
    """HEAD points at a tag: the repository has a default, but no branch of that name to start the task from."""
    project_repository.git("tag", "v1", "main")
    project_repository.git("symbolic-ref", "HEAD", "refs/tags/v1")
    refs_before = project_repository.git("for-each-ref")

    with pytest.raises(FoundryError, match=r"^the project repository has no commits to branch task/tst-0001 from$"):
        create(project_repository.project_tasks())
    assert project_repository.git("for-each-ref") == refs_before


def test_an_unreachable_repository_fails_with_the_message_from_git(tmp_path: Path, git_env) -> None:
    with pytest.raises(
        GitError, match=r"^git -C \S+ ls-remote --heads origin failed: .*does not appear to be a git repo"
    ):
        create(project_tasks_of(tmp_path / "missing.git", git_env))


# --- taken_task_ids -----------------------------------------------------------------------


def take_task_ids(project_repository, *, open_ids=(), closed_ids=(), branch_ids=(), keep_seeded=False) -> None:
    """Take task ids on the project repository: notes dirs for open and closed tasks, task branches from main for
    ``branch_ids``. The seeded tasks are removed unless ``keep_seeded``."""
    notes = {Task.as_open(task_id).task_file: f"{task_id}\n" for task_id in open_ids}
    notes |= {Task.as_closed(task_id).task_file: f"{task_id}\n" for task_id in closed_ids}
    project_repository.edit_notes(write=notes, remove=() if keep_seeded else project_repository.seeded_task_notes_dirs)
    for task_id in branch_ids:
        project_repository.git("branch", Task.as_open(task_id).branch, "main")


def test_taken_task_ids_are_the_open_closed_and_branch_ones_and_reading_them_changes_nothing(
    project_repository,
) -> None:
    take_task_ids(project_repository, open_ids=["wcf-0030"], closed_ids=["wcf-0032"], branch_ids=["wcf-0033"])
    refs_before = project_repository.git("for-each-ref")

    assert project_repository.project_tasks().taken_task_ids() == {"wcf-0030", "wcf-0032", "wcf-0033"}
    assert project_repository.git("for-each-ref") == refs_before


@pytest.mark.parametrize(
    "taken",
    [
        {"open_ids": ["wcf-0003", "wcf-0007"]},
        {"open_ids": ["wcf-0003"], "closed_ids": ["wcf-0007"]},
        {"open_ids": ["wcf-0003"], "branch_ids": ["wcf-0007"]},
    ],
    ids=["open", "closed", "branch"],
)
def test_the_highest_taken_number_counts_whichever_kind_holds_it(
    project_repository, taken: dict[str, list[str]]
) -> None:
    take_task_ids(project_repository, **taken)

    assert task.next_task_id(project_repository.project_tasks().taken_task_ids()) == "wcf-0008"


def test_names_that_aren_t_task_ids_are_not_taken_task_ids(project_repository) -> None:
    take_task_ids(project_repository, open_ids=["wcf-0005"])
    project_repository.edit_notes(write={f"{task.OPEN_DIR}/spike/TASK.md": "spike\n"})
    project_repository.git("branch", "task/spike", "main")
    project_repository.git("branch", "task/WCF-0099", "main")

    assert project_repository.project_tasks().taken_task_ids() == {"wcf-0005"}


def test_the_task_prefix_most_task_ids_use_is_followed(project_repository) -> None:
    take_task_ids(project_repository, open_ids=["wcf-0001", "wcf-0002"], keep_seeded=True)

    assert task.next_task_id(project_repository.project_tasks().taken_task_ids()) == "wcf-0003"


def test_a_task_s_branch_and_notes_count_as_one_task_id(project_repository) -> None:
    take_task_ids(project_repository, branch_ids=["sbx-0050", "sbx-0051", "sbx-0052"])
    for task_id in ("wcf-0001", "wcf-0002"):
        create(project_repository.project_tasks(), task_id)

    assert task.next_task_id(project_repository.project_tasks().taken_task_ids()) == "sbx-0053"


def test_without_task_branches_or_notes_no_task_id_is_taken(project_repository) -> None:
    project_repository.git("branch", "--quiet", "-D", task.NOTES_BRANCH)

    assert project_repository.project_tasks().taken_task_ids() == frozenset()


# --- fetch_task_turn ---------------------------------------------------------------------


def test_a_new_task_s_turn_is_the_template_s(project_repository) -> None:
    project_repository.project_tasks().create_task("tst-0001", {**TEMPLATE, "TURN": "dev\n"})

    assert project_repository.project_tasks().fetch_task_turn("tst-0001") == "dev"


@pytest.mark.parametrize(
    "files",
    [{}, {".agent/tasks/open/tst-0000/TURN": " \n\t"}, {".agent/tasks/open/tst-0000/TURN/dev": "dev\n"}],
    ids=["missing", "blank", "directory"],
)
def test_a_task_without_a_turn_is_refused_naming_its_turn_file(project_repository, files) -> None:
    if files:  # tst-0000 starts without a TURN
        project_repository.edit_notes(write=files)

    with pytest.raises(
        MissingTurnError,
        match=r"^task tst-0000 has no turn: agent-notes has no \.agent/tasks/open/tst-0000/TURN, or it is empty\.$",
    ):
        project_repository.project_tasks().fetch_task_turn("tst-0000")


def test_a_closed_task_s_turn_is_read_from_its_closed_task_notes_dir(project_repository) -> None:
    with pytest.raises(
        FoundryError, match=r"task cls-0000 has no turn: agent-notes has no .agent/tasks/closed/cls-0000/TURN"
    ):
        project_repository.project_tasks().fetch_task_turn("cls-0000")


def test_a_task_that_doesn_t_exist_has_no_turn_to_read(project_repository) -> None:
    with pytest.raises(TaskNotFoundError):
        project_repository.project_tasks().fetch_task_turn("tst-0009")


# --- fetch_task_turn_and_log ---------------------------------------------------------------


@pytest.mark.parametrize("task_id", ["tst-0000", "cls-0000"])
def test_a_task_s_turn_and_log_are_read_from_its_task_notes_dir(project_repository, task_id: str) -> None:
    found = project_repository.project_tasks().fetch_task(task_id)
    project_repository.edit_notes(
        write={found.turn_file: "  dev \n", found.log_file: "# Log\n\n## 1 · planner · planned\nDone.\n"}
    )

    assert project_repository.project_tasks().fetch_task_turn_and_log(task_id) == TaskTurnAndLog(
        found, "dev", "# Log\n\n## 1 · planner · planned\nDone.\n"
    )


TST_0000 = ".agent/tasks/open/tst-0000"
NO_TURN = r"^task tst-0000 has no turn: agent-notes has no \.agent/tasks/open/tst-0000/TURN, or it is empty\.$"
NO_LOG = r"^task tst-0000 has no LOG\.md: agent-notes has no file \.agent/tasks/open/tst-0000/LOG\.md$"


@pytest.mark.parametrize(
    "write, symlink, message",
    [
        ({f"{TST_0000}/LOG.md": "# Log\n"}, {}, NO_TURN),
        ({f"{TST_0000}/TURN/dev": "dev\n", f"{TST_0000}/LOG.md": "# Log\n"}, {}, NO_TURN),
        ({f"{TST_0000}/TURN": " \n\t", f"{TST_0000}/LOG.md": "# Log\n"}, {}, NO_TURN),
        (
            {f"{TST_0000}/LOG.md": "# Log\n"},
            {f"{TST_0000}/TURN": "/etc/hostname"},
            r"^task tst-0000's TURN is a link, and foundry reads only files: "
            r"agent-notes has a link at \.agent/tasks/open/tst-0000/TURN$",
        ),
        ({f"{TST_0000}/TURN": "dev\n"}, {}, NO_LOG),
        ({f"{TST_0000}/TURN": "dev\n", f"{TST_0000}/LOG.md/x": "x\n"}, {}, NO_LOG),
        (
            {f"{TST_0000}/TURN": "dev\n"},
            {f"{TST_0000}/LOG.md": "TASK.md"},
            r"^task tst-0000's LOG\.md is a link, and foundry reads only files: "
            r"agent-notes has a link at \.agent/tasks/open/tst-0000/LOG\.md$",
        ),
    ],
    ids=["turn-missing", "turn-dir", "turn-blank", "turn-link", "log-missing", "log-dir", "log-link"],
)
def test_a_malformed_task_s_turn_and_log_are_refused_naming_the_task_and_the_file(
    project_repository, write, symlink, message
) -> None:
    project_repository.edit_notes(write=write, symlink=symlink)

    with pytest.raises(FoundryError, match=message):
        project_repository.project_tasks().fetch_task_turn_and_log("tst-0000")


def test_a_task_that_doesn_t_exist_has_no_turn_and_log_to_read(project_repository) -> None:
    with pytest.raises(TaskNotFoundError):
        project_repository.project_tasks().fetch_task_turn_and_log("tst-0009")


# --- last_log_entry -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "log, entry",
    [
        ("# Log\n", None),
        ("", None),
        ("# Log\n\n## x · dev · progress\n  ## 3 · dev · indented\nx ## 4 · dev\n", None),
        (
            "# Log\n\n## 1 · planner · planned\nDone.\n\n## 2 · dev · progress\n\nDone: a.\n\n- Asks D1 → human: b?\n",
            "## 2 · dev · progress\n\nDone: a.\n\n- Asks D1 → human: b?",
        ),
        ("# Log\n\n## 12 · dev · progress\nDone.  \n \n\n\t\n", "## 12 · dev · progress\nDone."),
        (
            "## 1 · dev · progress\n## 2 · dev · progress\n  ## 3 · dev · x\n## x · dev\nend",
            "## 2 · dev · progress\n  ## 3 · dev · x\n## x · dev\nend",
        ),
    ],
    ids=[
        "template",
        "empty",
        "no-heading-at-line-start",
        "blank-lines-inside",
        "trailing-blanks-multi-digit",
        "no-final-newline",
    ],
)
def test_the_last_log_entry_runs_from_the_last_heading_to_the_end_without_trailing_blanks(log, entry) -> None:
    assert last_log_entry(log) == entry


# --- fetch_task ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "task_id, found", [("tst-0000", Task.as_open("tst-0000")), ("cls-0000", Task.as_closed("cls-0000"))]
)
def test_a_task_has_the_status_of_the_dir_holding_its_notes(project_repository, task_id: str, found) -> None:
    assert project_repository.project_tasks().fetch_task(task_id) == found


def test_a_task_in_neither_dir_is_not_found_naming_both(project_repository) -> None:
    with pytest.raises(
        TaskNotFoundError,
        match=(
            r"^task tst-0009 doesn't exist: "
            r"agent-notes has neither .agent/tasks/open/tst-0009/ nor .agent/tasks/closed/tst-0009/$"
        ),
    ):
        project_repository.project_tasks().fetch_task("tst-0009")


def test_finding_a_task_without_a_notes_branch_names_the_missing_branch(tmp_path: Path, git_env) -> None:
    bare_dir = tmp_path / "bare.git"
    git_output(git_env, "init", "--quiet", "--bare", str(bare_dir))
    with pytest.raises(BranchNotFoundError, match=r"^the project repository has no agent-notes branch$"):
        project_tasks_of(bare_dir, git_env).fetch_task("tst-0001")


@pytest.mark.parametrize(
    "operation",
    [
        lambda project_tasks: project_tasks.fetch_task("tst-0000"),
        lambda project_tasks: project_tasks.fetch_task_turn("tst-0000"),
        lambda project_tasks: project_tasks.fetch_open_task_turns(),
        lambda project_tasks: project_tasks.close_task("cls-0000"),  # refused: already closed
        lambda project_tasks: project_tasks.hand_off("cls-0000", "dev", note=None),  # refused: closed
        lambda project_tasks: project_tasks.create_task("cls-0000", TEMPLATE),  # refused: exists, closed
    ],
    ids=[
        "fetch_task",
        "fetch_task_turn",
        "fetch_open_task_turns",
        "refused-close",
        "refused-hand-off",
        "refused-create",
    ],
)
def test_finding_reading_and_refusing_change_no_file(project_repository, git_env, tmp_path: Path, operation) -> None:
    """Only an operation that goes ahead checks out NOTES_BRANCH; until then the clone's working tree is empty."""
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/TURN": "dev\n"})
    work_dir = tmp_path / "clone"
    work_dir.mkdir()
    project_tasks = ProjectTasks(ProjectScratchClone.init(str(project_repository.path), work_dir, git_env))

    with contextlib.suppress(FoundryError):
        operation(project_tasks)

    assert [path.name for path in work_dir.iterdir()] == [".git"]


def test_a_task_in_both_dirs_is_refused_naming_both(project_repository) -> None:
    project_repository.edit_notes(write={".agent/tasks/closed/tst-0000/TASK.md": "tst-0000\n"})

    with pytest.raises(
        FoundryError, match=r"^task tst-0000 is both open and closed: .*open/tst-0000/ and .*closed/tst-0000/$"
    ) as error:
        project_repository.project_tasks().fetch_task("tst-0000")
    assert not isinstance(error.value, TaskNotFoundError)


# --- close_task, reopen_task -------------------------------------------------------------


def moved(files: dict[str, str], src: str, dst: str) -> dict[str, str]:
    """``files``, by path, with the ones under the notes dir ``src`` now under ``dst``."""
    return {
        dst + path.removeprefix(src) if path.startswith(f"{src}/") else path: entry for path, entry in files.items()
    }


def test_close_moves_the_task_notes_dir_unchanged_in_one_signed_commit(project_repository) -> None:
    project_repository.edit_notes(
        write={
            ".agent/tasks/open/tst-0000/sub/NOTE.md": "n\n",
            ".agent/tasks/open/tst-0000/PROGRESS.md": "p\n",
            ".agent/tasks/open/tst-00001/TASK.md": "tst-00001\n",
        },
    )
    before = project_repository.notes_files()
    commits_before = len(project_repository.notes_commits())
    branches_before = project_repository.git("branch", "--list")

    assert project_repository.project_tasks().close_task("tst-0000") == Task.as_closed("tst-0000")

    expected = moved(before, ".agent/tasks/open/tst-0000", ".agent/tasks/closed/tst-0000")
    assert project_repository.notes_files() == expected
    assert ".agent/tasks/closed/tst-0000/sub/NOTE.md" in expected
    assert ".agent/tasks/open/tst-00001/TASK.md" in expected
    assert project_repository.notes_commits()[0] == "Close task tst-0000"
    assert len(project_repository.notes_commits()) == commits_before + 1
    assert project_repository.notes_signed_with_your_key()
    assert project_repository.git("branch", "--list") == branches_before


def test_reopen_makes_the_reverse_move_in_one_signed_commit(project_repository) -> None:
    before = project_repository.notes_files()

    assert project_repository.project_tasks().reopen_task("cls-0000") == Task.as_open("cls-0000")

    expected = moved(before, ".agent/tasks/closed/cls-0000", ".agent/tasks/open/cls-0000")
    assert project_repository.notes_files() == expected
    assert project_repository.notes_commits()[0] == "Reopen task cls-0000"
    assert project_repository.notes_signed_with_your_key()


def test_a_move_keeps_files_your_git_config_would_ignore_or_convert(project_repository, git_env) -> None:
    project_repository.edit_notes(
        write={".agent/tasks/open/tst-0000/run.log": "log\n", ".agent/tasks/open/tst-0000/crlf.md": "a\r\nb\r\n"},
    )
    home_dir = Path(git_env["HOME"])
    (home_dir / "excludes").write_text("*.log\n")
    with (home_dir / ".gitconfig").open("a") as gitconfig:
        gitconfig.write(f"[core]\n\texcludesFile = {home_dir / 'excludes'}\n\tautocrlf = input\n")
    before = project_repository.notes_tree()

    project_repository.project_tasks().close_task("tst-0000")

    assert project_repository.notes_tree() == moved(
        before, ".agent/tasks/open/tst-0000", ".agent/tasks/closed/tst-0000"
    )


@pytest.mark.parametrize(
    "operation, task_id, message",
    [
        (ProjectTasks.close_task, "cls-0000", "^task cls-0000 is already closed$"),
        (ProjectTasks.close_task, "tst-0009", r"^task tst-0009 doesn't exist: "),
        (ProjectTasks.reopen_task, "tst-0000", "^task tst-0000 is already open$"),
        (ProjectTasks.reopen_task, "tst-0009", r"^task tst-0009 doesn't exist: "),
    ],
)
def test_close_and_reopen_refuse_and_push_nothing(project_repository, operation, task_id, message) -> None:
    notes_before = project_repository.notes_head()

    with pytest.raises(FoundryError, match=message):
        operation(project_repository.project_tasks(), task_id)
    assert project_repository.notes_head() == notes_before


@pytest.mark.parametrize(
    "operation, task_id",
    [(ProjectTasks.close_task, "tst-0000"), (ProjectTasks.reopen_task, "cls-0000")],
    ids=["close", "reopen"],
)
def test_without_a_signing_key_close_and_reopen_push_nothing(
    project_repository, no_signing_key, operation, task_id
) -> None:
    notes_before = project_repository.notes_head()

    with pytest.raises(GitError, match=r"(?s)commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"):
        operation(project_repository.project_tasks(), task_id)
    assert project_repository.notes_head() == notes_before


# --- log_with_handoff_entry -----------------------------------------------------------------


@pytest.mark.parametrize(
    "log, turn, note, expected",
    [
        ("", "dev", None, "## 1 · human · handoff\nTurn: dev.\n"),
        (" \n\n", "dev", None, "## 1 · human · handoff\nTurn: dev.\n"),
        ("# Log\n", "human", None, "# Log\n\n## 1 · human · handoff\nTurn: human.\n"),
        ("# Log\n\n\n \t\n", "dev", None, "# Log\n\n## 1 · human · handoff\nTurn: dev.\n"),
        (
            "# Log\n\n## 1 · planner · planned\nDone.\n\n## 2 · dev · progress\nDone.\n",
            "dev",
            "  look at R3  ",
            "# Log\n\n## 1 · planner · planned\nDone.\n\n## 2 · dev · progress\nDone.\n"
            "\n## 3 · human · handoff\nTurn: dev.\nNote: look at R3\n",
        ),
        (
            "# Log\n\n## 12 · dev · progress\n\n## 4 · reviewer · changes-needed\nSee REVIEW.md.",
            "dev",
            None,
            "# Log\n\n## 12 · dev · progress\n\n## 4 · reviewer · changes-needed\nSee REVIEW.md.\n"
            "\n## 5 · human · handoff\nTurn: dev.\n",
        ),
        (
            "# Log\n\n## 7 · dev · progress\n  ## 9 · dev · indented\n## 10 · \n## 11 · x\n## x · dev\n",
            "dev",
            None,
            "# Log\n\n## 7 · dev · progress\n  ## 9 · dev · indented\n## 10 · \n## 11 · x\n## x · dev\n"
            "\n## 12 · human · handoff\nTurn: dev.\n",
        ),
    ],
    ids=[
        "empty",
        "blank",
        "no-entries-to-human",
        "trailing-blank-lines",
        "entries-with-note",
        "last-heading-not-highest-no-final-newline",
        "only-numbered-headings-at-line-start-count",
    ],
)
def test_the_handoff_entry_follows_the_log_after_one_blank_line_numbered_after_its_last_entry(
    log, turn, note, expected
) -> None:
    """The log's text is kept, but for the whitespace at its end."""
    assert log_with_handoff_entry(log, turn=turn, note=note) == expected


# --- handoff ------------------------------------------------------------------------------

LOG = "# Log\n\n## 1 · planner · planned\nDone.\n"


@pytest.mark.parametrize(
    "turn_files",
    [{".agent/tasks/open/tst-0000/TURN": " reviewer \n"}, {}, {".agent/tasks/open/tst-0000/TURN": " \n\t"}],
    ids=["a-turn", "no-turn", "blank-turn"],
)
def test_handoff_writes_turn_and_appends_to_the_log_in_one_signed_commit(project_repository, turn_files) -> None:
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/LOG.md": LOG, **turn_files})
    files_before = project_repository.notes_files()
    commits_before = len(project_repository.notes_commits())

    project_repository.project_tasks().hand_off("tst-0000", "dev", note=" see R2 ")
    expected_log = LOG + "\n## 2 · human · handoff\nTurn: dev.\nNote: see R2\n"
    assert project_repository.notes_files() == {
        **files_before,
        ".agent/tasks/open/tst-0000/TURN": "dev\n",
        ".agent/tasks/open/tst-0000/LOG.md": expected_log,
    }
    assert project_repository.notes_commits()[0] == "Handoff of task tst-0000 to dev"
    assert len(project_repository.notes_commits()) == commits_before + 1
    assert project_repository.notes_signed_with_your_key()


@pytest.mark.parametrize(
    "task_id, edits, error, message",
    [
        ("tst-0009", {}, TaskNotFoundError, r"^task tst-0009 doesn't exist: "),
        ("cls-0000", {}, ClosedTaskError, r"^task cls-0000 is closed$"),
        (
            "tst-0000",
            # with a LOG.md, so the turn is what is refused, whatever order the checks run in
            {"write": {".agent/tasks/open/tst-0000/TURN": "dev\n", ".agent/tasks/open/tst-0000/LOG.md": LOG}},
            FoundryError,
            r"^task tst-0000's turn is already dev$",
        ),
        (
            "tst-0000",
            {},
            FoundryError,
            r"^task tst-0000 has no LOG\.md: agent-notes has no file \.agent/tasks/open/tst-0000/LOG\.md$",
        ),
        (
            "tst-0000",
            {"write": {".agent/tasks/open/tst-0000/LOG.md/x": "x\n"}},
            FoundryError,
            r"^task tst-0000 has no LOG\.md: agent-notes has no file \.agent/tasks/open/tst-0000/LOG\.md$",
        ),
        (
            "tst-0000",
            {"write": {".agent/LOG.md": LOG}, "symlink": {".agent/tasks/open/tst-0000/LOG.md": "../../../LOG.md"}},
            FoundryError,
            r"^\.agent/tasks/open/tst-0000/LOG\.md is a link: foundry writes only files$",
        ),
        (
            "tst-0000",
            # with a LOG.md, so the link TURN is what is refused
            {
                "write": {".agent/TURN": "human\n", ".agent/tasks/open/tst-0000/LOG.md": LOG},
                "symlink": {".agent/tasks/open/tst-0000/TURN": "../../../TURN"},
            },
            FoundryError,
            r"^\.agent/tasks/open/tst-0000/TURN is a link: foundry writes only files$",
        ),
    ],
    ids=[
        "not-found",
        "closed",
        "same-turn",
        "no-log",
        "log-is-a-dir",
        "log-is-a-link",
        "turn-is-a-link",
    ],
)
def test_handoff_refuses_and_pushes_nothing(project_repository, task_id, edits, error, message) -> None:
    if edits:
        project_repository.edit_notes(**edits)
    notes_before = project_repository.notes_head()

    with pytest.raises(error, match=message) as raised:
        project_repository.project_tasks().hand_off(task_id, "dev", note=None)
    assert type(raised.value) is error
    assert project_repository.notes_head() == notes_before


def test_without_a_signing_key_handoff_pushes_nothing(project_repository, no_signing_key) -> None:
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/LOG.md": LOG})
    notes_before = project_repository.notes_head()

    with pytest.raises(GitError, match=r"(?s)commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"):
        project_repository.project_tasks().hand_off("tst-0000", "dev", note=None)
    assert project_repository.notes_head() == notes_before


# --- fetch_open_task_turns -----------------------------------------------------------


def task_turns_of(project_tasks: ProjectTasks) -> list[tuple[str, str]]:
    found = project_tasks.fetch_open_task_turns()
    assert all(task_turn.task.status is Status.OPEN for task_turn in found)
    return [(task_turn.task.id, task_turn.turn) for task_turn in found]


def test_open_tasks_are_listed_in_id_order_with_their_stripped_turns(project_repository) -> None:
    project_repository.edit_notes(
        write={
            ".agent/tasks/open/tst-0000/TURN": "dev\n",
            ".agent/tasks/open/bbb-0001/TURN": "  human \n\n",
            ".agent/tasks/open/aaa-0002/TURN": "reviewer",
            ".agent/tasks/closed/cls-0000/TURN": "dev\n",  # closed: left out
            ".agent/tasks/open/stray.txt": "not a task\n",  # a file: ignored
        },
    )

    assert task_turns_of(project_repository.project_tasks()) == [
        ("aaa-0002", "reviewer"),
        ("bbb-0001", "human"),
        ("tst-0000", "dev"),
    ]
    assert isinstance(project_repository.project_tasks().fetch_open_task_turns()[0], TaskTurn)


def test_a_symlinked_turn_shows_the_link_s_target_name_and_reads_nothing_outside(project_repository) -> None:
    project_repository.edit_notes(symlink={".agent/tasks/open/tst-0000/TURN": "/etc/hostname"})

    assert task_turns_of(project_repository.project_tasks()) == [("tst-0000", "/etc/hostname")]


def test_no_open_dir_after_the_last_task_closed_lists_nothing(project_repository) -> None:
    project_repository.edit_notes(remove=[".agent/tasks/open"])

    assert task_turns_of(project_repository.project_tasks()) == []


@pytest.mark.parametrize(
    "files",
    [{}, {".agent/tasks/open/tst-0000/TURN": " \n\t"}, {".agent/tasks/open/tst-0000/TURN/dev": "dev\n"}],
    ids=["missing", "blank", "directory"],
)
def test_listing_fails_on_a_task_without_a_turn(project_repository, files) -> None:
    if files:  # tst-0000 starts without a TURN
        project_repository.edit_notes(write=files)

    with pytest.raises(
        MissingTurnError,
        match=r"^task tst-0000 has no turn: agent-notes has no \.agent/tasks/open/tst-0000/TURN, or it is empty\.$",
    ):
        task_turns_of(project_repository.project_tasks())


def test_a_dir_that_is_not_a_task_id_fails_naming_it(project_repository) -> None:
    project_repository.edit_notes(
        write={".agent/tasks/open/tst-0000/TURN": "dev\n", ".agent/tasks/open/Bad Dir/TURN": "dev"}
    )

    with pytest.raises(
        FoundryError,
        match=r"^.agent/tasks/open/Bad Dir/ is not a valid task id \(task id 'Bad Dir' is not valid: "
        r"use lowercase letters, .*\)\. Rename or remove it\.$",
    ):
        task_turns_of(project_repository.project_tasks())


def test_a_repository_without_a_notes_branch_lists_no_open_task(tmp_path: Path, git_env) -> None:
    """No task has been created yet, so there is no agent-notes: that is no task, not an error."""
    bare_dir = tmp_path / "bare.git"
    git_output(git_env, "init", "--quiet", "--bare", str(bare_dir))

    assert task_turns_of(project_tasks_of(bare_dir, git_env)) == []


def test_listing_an_unreachable_repository_fails_with_the_message_from_git(tmp_path: Path, git_env) -> None:
    with pytest.raises(GitError, match=r"ls-remote --heads origin failed: .*does not appear to be a git repo"):
        task_turns_of(project_tasks_of(tmp_path / "missing.git", git_env))


def test_listing_costs_one_fetch_however_many_tasks(project_repository, git_env, tmp_path: Path) -> None:
    project_repository.edit_notes(write={f".agent/tasks/open/tst-{n:04}/TURN": "dev\n" for n in range(6)})
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    git_calls = counting_stand_in(shim_dir, "git")
    counting_env = {**git_env, "PATH": f"{shim_dir}:{git_env['PATH']}"}

    found = project_repository.project_tasks(env=counting_env).fetch_open_task_turns()

    assert len(found) == 6
    assert fetch_count(git_calls) == 1


# --- foundry task list: the lines and the arguments -----------------------------------------

# --- an id given in uppercase ------------------------------------------------------------


@pytest.mark.parametrize(
    "operation, task_id",
    [
        (ProjectTasks.create_task, "TST-0001"),
        (ProjectTasks.create_task, "TST-0000"),
        (ProjectTasks.close_task, "TST-0000"),
        (ProjectTasks.reopen_task, "CLS-0000"),
        (ProjectTasks.fetch_task, "TST-0000"),
    ],
    ids=["create", "create-existing", "close", "reopen", "get"],
)
def test_an_uppercase_id_is_refused_not_lowercased_and_nothing_is_pushed(
    project_repository, operation, task_id: str
) -> None:
    project_tasks = project_repository.project_tasks()
    args = (task_id, TEMPLATE) if operation is ProjectTasks.create_task else (task_id,)
    refs_before = project_repository.git("for-each-ref")

    with pytest.raises(FoundryError, match=rf"^task id '{task_id}' is not valid: ") as error:
        operation(project_tasks, *args)
    assert not isinstance(error.value, TaskNotFoundError)
    assert project_repository.git("for-each-ref") == refs_before
