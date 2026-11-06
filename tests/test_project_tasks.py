"""ProjectTasks against a real repository on disk: creating, finding, closing, reopening and handing off tasks,
and reading and listing their turns."""

import subprocess
from pathlib import Path

import pytest

from agent_runtime.git import GitError
from foundry import task
from foundry.errors import FoundryError
from foundry.project_tasks import (
    ClosedTaskError,
    MissingTurnError,
    ProjectTasks,
    TaskNotFoundError,
    TaskSummary,
    log_with_handoff_entry,
)
from foundry.task import Status, Task
from tests.support.project_repository import git_output, project_tasks_of

TEMPLATE = {"TASK.md": "# Task <id>: <title>\n", "PROGRESS.md": "# Progress\n"}


@pytest.fixture
def no_signing_key(git_env) -> None:
    """Your git config, without a signing key."""
    git_output(git_env, "config", "--global", "--unset", "user.signingkey")


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


def test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files(project_repository) -> None:
    project_repository.git("branch", "--quiet", "-D", task.NOTES_BRANCH)

    create(project_repository.project_tasks())

    assert project_repository.notes_files() == {
        ".agent/tasks/open/tst-0001/PROGRESS.md": "# Progress\n",
        ".agent/tasks/open/tst-0001/TASK.md": "# Task <id>: <title>\n",
    }
    assert project_repository.git("rev-list", "--count", task.NOTES_BRANCH) == "1"


def test_the_tasks_notes_commit_is_signed_with_your_signing_key(project_repository) -> None:
    create(project_repository.project_tasks())

    assert project_repository.notes_signed_with_your_key()


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

    with pytest.raises(FoundryError, match=r"^the repository has no commits to branch task/tst-0001 from$"):
        create(project_tasks_of(empty_dir, git_env))


def test_an_unreachable_repository_fails_with_gits_message(tmp_path: Path, git_env) -> None:
    with pytest.raises(
        GitError, match=r"^git -C \S+ ls-remote --heads origin failed: .*does not appear to be a git repo"
    ):
        create(project_tasks_of(tmp_path / "missing.git", git_env))


# --- read_task_turn ---------------------------------------------------------------------


def test_a_new_task_s_turn_is_the_template_s(project_repository) -> None:
    project_repository.project_tasks().create_task("tst-0001", {**TEMPLATE, "TURN": "dev\n"})

    assert project_repository.project_tasks().read_task_turn("tst-0001") == "dev"


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
        project_repository.project_tasks().read_task_turn("tst-0000")


def test_a_closed_task_s_turn_is_read_from_its_closed_task_notes_dir(project_repository) -> None:
    with pytest.raises(
        FoundryError, match=r"task cls-0000 has no turn: agent-notes has no .agent/tasks/closed/cls-0000/TURN"
    ):
        project_repository.project_tasks().read_task_turn("cls-0000")


def test_a_task_that_doesn_t_exist_has_no_turn_to_read(project_repository) -> None:
    with pytest.raises(TaskNotFoundError):
        project_repository.project_tasks().read_task_turn("tst-0009")


# --- get_task_by_id ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "task_id, found", [("tst-0000", Task.as_open("tst-0000")), ("cls-0000", Task.as_closed("cls-0000"))]
)
def test_a_task_has_the_status_of_the_dir_holding_its_notes(project_repository, task_id: str, found) -> None:
    assert project_repository.project_tasks().get_task_by_id(task_id) == found


def test_a_task_in_neither_dir_is_not_found_naming_both(project_repository) -> None:
    with pytest.raises(
        TaskNotFoundError,
        match=(
            r"^task tst-0009 doesn't exist: "
            r"agent-notes has neither .agent/tasks/open/tst-0009/ nor .agent/tasks/closed/tst-0009/$"
        ),
    ):
        project_repository.project_tasks().get_task_by_id("tst-0009")


def test_a_repository_without_a_notes_branch_has_no_tasks(tmp_path: Path, git_env) -> None:
    bare_dir = tmp_path / "bare.git"
    git_output(git_env, "init", "--quiet", "--bare", str(bare_dir))
    with pytest.raises(TaskNotFoundError):
        project_tasks_of(bare_dir, git_env).get_task_by_id("tst-0001")


def test_a_task_in_both_dirs_is_refused_naming_both(project_repository) -> None:
    project_repository.edit_notes(write={".agent/tasks/closed/tst-0000/TASK.md": "tst-0000\n"})

    with pytest.raises(
        FoundryError, match=r"^task tst-0000 is both open and closed: .*open/tst-0000/ and .*closed/tst-0000/$"
    ) as error:
        project_repository.project_tasks().get_task_by_id("tst-0000")
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

    project_repository.project_tasks().handoff("tst-0000", "dev", note=" see R2 ")
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
        project_repository.project_tasks().handoff(task_id, "dev", note=None)
    assert type(raised.value) is error
    assert project_repository.notes_head() == notes_before


def test_without_a_signing_key_handoff_pushes_nothing(project_repository, no_signing_key) -> None:
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/LOG.md": LOG})
    notes_before = project_repository.notes_head()

    with pytest.raises(GitError, match=r"(?s)commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"):
        project_repository.project_tasks().handoff("tst-0000", "dev", note=None)
    assert project_repository.notes_head() == notes_before


# --- list_open_task_summaries -----------------------------------------------------------


def summaries_of(project_tasks: ProjectTasks) -> list[tuple[str, str]]:
    found = project_tasks.list_open_task_summaries()
    assert all(summary.task.status is Status.OPEN for summary in found)
    return [(summary.task.id, summary.turn) for summary in found]


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

    assert summaries_of(project_repository.project_tasks()) == [
        ("aaa-0002", "reviewer"),
        ("bbb-0001", "human"),
        ("tst-0000", "dev"),
    ]
    assert isinstance(project_repository.project_tasks().list_open_task_summaries()[0], TaskSummary)


def test_a_symlinked_turn_shows_the_link_s_target_name_and_reads_nothing_outside(project_repository) -> None:
    project_repository.edit_notes(symlink={".agent/tasks/open/tst-0000/TURN": "/etc/hostname"})

    assert summaries_of(project_repository.project_tasks()) == [("tst-0000", "/etc/hostname")]


def test_no_open_dir_after_the_last_task_closed_lists_nothing(project_repository) -> None:
    project_repository.edit_notes(remove=[".agent/tasks/open"])

    assert summaries_of(project_repository.project_tasks()) == []


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
        summaries_of(project_repository.project_tasks())


def test_a_dir_that_is_not_a_task_id_fails_naming_it(project_repository) -> None:
    project_repository.edit_notes(
        write={".agent/tasks/open/tst-0000/TURN": "dev\n", ".agent/tasks/open/Bad Dir/TURN": "dev"}
    )

    with pytest.raises(
        FoundryError,
        match=r"^.agent/tasks/open/Bad Dir/ is not a valid task id \(task id 'Bad Dir' is not valid: "
        r"use lowercase letters, .*\)\. Rename or remove it\.$",
    ):
        summaries_of(project_repository.project_tasks())


def test_listing_a_repository_without_a_notes_branch_names_agent_notes(tmp_path: Path, git_env) -> None:
    bare_dir = tmp_path / "bare.git"
    git_output(git_env, "init", "--quiet", "--bare", str(bare_dir))

    with pytest.raises(FoundryError, match=r"^the repository has no agent-notes branch$"):
        summaries_of(project_tasks_of(bare_dir, git_env))


def test_listing_an_unreachable_repository_fails_with_gits_message(tmp_path: Path, git_env) -> None:
    with pytest.raises(GitError, match=r"ls-remote --heads origin failed: .*does not appear to be a git repo"):
        summaries_of(project_tasks_of(tmp_path / "missing.git", git_env))


def test_listing_costs_one_fetch_however_many_tasks(project_repository, git_env, tmp_path: Path) -> None:
    project_repository.edit_notes(write={f".agent/tasks/open/tst-{n:04}/TURN": "dev\n" for n in range(6)})
    log = tmp_path / "git-calls.log"
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    real_git = subprocess.run(["which", "git"], env=git_env, capture_output=True, text=True, check=True).stdout.strip()
    shim = shim_dir / "git"
    shim.write_text(f'#!/bin/sh\necho "$*" >> {log}\nexec {real_git} "$@"\n')
    shim.chmod(0o755)
    counting_env = {**git_env, "PATH": f"{shim_dir}:{git_env['PATH']}"}

    found = project_repository.project_tasks(env=counting_env).list_open_task_summaries()

    assert len(found) == 6
    assert sum(" fetch " in f" {line} " for line in log.read_text().splitlines()) == 1


# --- foundry task list: the lines and the arguments -----------------------------------------

# --- an id given in uppercase ------------------------------------------------------------


@pytest.mark.parametrize(
    "operation, task_id",
    [
        (ProjectTasks.create_task, "TST-0001"),
        (ProjectTasks.create_task, "TST-0000"),
        (ProjectTasks.close_task, "TST-0000"),
        (ProjectTasks.reopen_task, "CLS-0000"),
        (ProjectTasks.get_task_by_id, "TST-0000"),
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
