"""The `foundry task` commands: their reports, arguments and checks, and end to end through cli.main."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from foundry import cli
from foundry.commands.task import (
    CLOSED,
    CREATED,
    REOPENED,
    Outcome,
    ProjectListing,
    chosen_projects,
    filter_project_listing,
    handoff_lines,
    listing_lines,
    read_listings_and_errors,
    report,
    require_valid_handoff_args,
    show_lines,
)
from foundry.config import Config, Project, Role
from foundry.errors import FoundryError
from foundry.project_tasks import TaskTurn, TaskTurnAndLog
from foundry.task import Task
from tests.support import ProcessEnvironment
from tests.support.foundry_root import write_foundry
from tests.support.machine import counting_stand_in
from tests.support.project_repository import ProjectRepository, fetch_count, git_output

# --- the command ------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome, changed, lines",
    [
        (
            CREATED,
            Task.as_open("tst-0001"),
            ["created task tst-0001 in store", "run it with: foundry run store tst-0001"],
        ),
        (
            CLOSED,
            Task.as_closed("tst-0001"),
            ["closed task tst-0001 in store", "reopen it with: foundry task reopen store tst-0001"],
        ),
        (
            REOPENED,
            Task.as_open("tst-0001"),
            ["reopened task tst-0001 in store", "run it with: foundry run store tst-0001"],
        ),
    ],
)
def test_the_report_says_what_was_done_and_what_comes_next(outcome: Outcome, changed: Task, lines: list[str]) -> None:
    assert report(outcome, "store", changed) == lines


def test_create_takes_a_project_and_a_task() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "tst-0001"])
    assert (args.project_name, args.task_id) == ("store", "tst-0001")


@pytest.mark.parametrize("action", ["close", "reopen"])
def test_close_and_reopen_take_a_project_and_a_task(action: str) -> None:
    args = cli.build_parser().parse_args(["task", action, "store", "tst-0001"])
    assert (args.project_name, args.task_id) == ("store", "tst-0001")


def test_create_close_and_reopen_print_what_they_did_or_an_error_and_exit_accordingly(
    project_repository, enter_foundry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real commands, in a foundry of its own: each one's output and exit code, for a change and for
    a refusal."""
    foundry_root = write_foundry(tmp_path / "foundry", {"store": project_repository.path})
    (foundry_root / "config" / "task-template").mkdir()
    (foundry_root / "config" / "task-template" / "TASK.md").write_text("# Task\n")
    enter_foundry(foundry_root)

    assert cli.main(["task", "create", "store", "tst-0001"]) == 0
    assert capsys.readouterr() == (
        "created task tst-0001 in store\nrun it with: foundry run store tst-0001\n",
        "",
    )
    assert cli.main(["task", "close", "store", "tst-0001"]) == 0
    assert capsys.readouterr() == (
        "closed task tst-0001 in store\nreopen it with: foundry task reopen store tst-0001\n",
        "",
    )
    assert cli.main(["task", "reopen", "store", "tst-0001"]) == 0
    assert capsys.readouterr() == (
        "reopened task tst-0001 in store\nrun it with: foundry run store tst-0001\n",
        "",
    )
    assert project_repository.notes_files()[".agent/tasks/open/tst-0001/TASK.md"] == "# Task\n"

    for action, task_id, error in [
        ("create", "tst-0001", "task tst-0001 already exists: agent-notes has .agent/tasks/open/tst-0001/"),
        ("close", "cls-0000", "task cls-0000 is already closed"),
        ("reopen", "tst-0000", "task tst-0000 is already open"),
    ]:
        assert cli.main(["task", action, "store", task_id]) == 1
        assert capsys.readouterr() == ("", f"error: {error}\n")


# --- foundry task list: the lines and the arguments -----------------------------------------


def listing(name: str, *turns: tuple[str, str]) -> ProjectListing:
    return ProjectListing(name, [TaskTurn(Task.as_open(task_id), turn) for task_id, turn in turns])


def test_task_lines_are_aligned_across_every_project_with_two_spaces_between_columns() -> None:
    stdout_lines, stderr_lines = listing_lines(
        [listing("store", ("wcf-0007", "dev"), ("wcf-0010", "human")), listing("a", ("t-0001", "reviewer"))],
        [],
    )

    assert stdout_lines == [
        "store  wcf-0007  dev",
        "store  wcf-0010  human",
        "a      t-0001    reviewer",
    ]
    assert stderr_lines == []


def test_turn_keeps_only_the_tasks_whose_turn_is_exactly_that() -> None:
    store = listing("store", ("tst-0001", "dev"), ("tst-0002", "developer"), ("tst-0003", "dev"), ("tst-0004", "Dev"))

    kept = filter_project_listing(store, "dev")

    assert kept.project_name == "store"
    assert kept.task_turns == listing("store", ("tst-0001", "dev"), ("tst-0003", "dev")).task_turns
    assert len(store.task_turns) == 4  # a new listing; the one given is left as it was


def test_no_turn_keeps_the_listing_as_it_is() -> None:
    store = listing("store", ("tst-0001", "dev"))

    assert filter_project_listing(store, None) is store


def test_a_project_without_tasks_is_a_line_outside_the_columns() -> None:
    stdout_lines, _ = listing_lines([listing("empty-and-long"), listing("store", ("wcf-0007", "dev"))], [])

    assert stdout_lines == [
        "empty-and-long  no open tasks",
        "store  wcf-0007  dev",
    ]  # its name doesn't widen the column


def test_turn_with_open_tasks_but_none_matching_says_so() -> None:
    stdout_lines, _ = listing_lines(
        [
            filter_project_listing(listing("store", ("tst-0001", "dev")), "human"),
            filter_project_listing(listing("empty"), "human"),
        ],
        [],
    )

    assert stdout_lines == ["store  no open tasks with turn human", "empty  no open tasks"]


def test_a_failed_project_is_an_error_line_and_the_others_are_still_listed() -> None:
    stdout_lines, stderr_lines = listing_lines([listing("store", ("tst-0001", "dev"))], [FoundryError("bad: boom")])

    assert (stdout_lines, stderr_lines) == (["store  tst-0001  dev"], ["error: bad: boom"])


def test_list_takes_optional_projects_and_a_turn() -> None:
    parse = cli.build_parser().parse_args
    assert (parse(["task", "list"]).project_names, parse(["task", "list"]).turn) == ([], None)
    args = parse(["task", "list", "store", "blog", "--turn", "human"])
    assert (args.project_names, args.turn) == (["store", "blog"], "human")


def test_chosen_projects_are_in_name_order_once_each_and_all_when_none_are_named() -> None:
    foundry_config = Config("f", {name: Project(name, f"url/{name}") for name in ("store", "blog")}, {})

    assert [p.name for p in chosen_projects(foundry_config, [])] == ["blog", "store"]
    assert [p.name for p in chosen_projects(foundry_config, ["store", "blog", "store"])] == ["blog", "store"]


def test_an_unknown_project_is_refused_as_create_refuses_it() -> None:
    foundry_config = Config("f", {"store": Project("store", "url")}, {})

    with pytest.raises(FoundryError, match=r"^unknown project 'nope'; known: store$"):
        chosen_projects(foundry_config, ["store", "nope"])


def test_each_project_gives_a_listing_or_an_error_naming_it(project_repository, git_env, tmp_path: Path) -> None:
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/TURN": "dev\n"})
    git_output(git_env, "init", "--quiet", "--bare", str(tmp_path / "bare.git"))  # no agent-notes: no task yet
    projects = [
        Project("bare", str(tmp_path / "bare.git")),
        Project("gone", str(tmp_path / "missing.git")),  # unreachable: git's GitError
        Project("store", str(project_repository.path)),
    ]

    listings, errors = read_listings_and_errors(projects, git_env)

    assert listings == [
        ProjectListing("bare", []),
        ProjectListing("store", [TaskTurn(Task.as_open("tst-0000"), "dev")]),
    ]
    assert [type(error) for error in errors] == [FoundryError]
    assert str(errors[0]).startswith("gone: ") and "does not appear to be a git repo" in str(errors[0])


def test_list_prints_tasks_on_stdout_errors_on_stderr_and_exits_1_if_a_project_failed(
    project_repository, enter_foundry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, in a foundry of its own: one project lists, the other can't be reached."""
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/TURN": "dev\n"})
    foundry_root = write_foundry(
        tmp_path / "foundry", {"store": project_repository.path, "gone": tmp_path / "missing.git"}
    )
    enter_foundry(foundry_root)

    assert cli.main(["task", "list"]) == 1
    printed = capsys.readouterr()
    assert printed.out == "store  tst-0000  dev\n"
    assert printed.err.startswith("error: gone: ") and printed.err.count("error: ") == 1

    assert cli.main(["task", "list", "store"]) == 0
    assert capsys.readouterr() == ("store  tst-0000  dev\n", "")

    assert cli.main(["task", "list", "store", "--turn", "human"]) == 0
    assert capsys.readouterr() == ("store  no open tasks with turn human\n", "")


# --- foundry task handoff ---------------------------------------------------------------

HANDOFF_CONFIG = Config(
    "f",
    {"store": Project("store", "url")},
    {name: Role(name, Path(f"/secrets/ssh/{name}"), None) for name in ("reviewer", "dev")},
)


@pytest.mark.parametrize("turn, note", [("dev", None), ("human", "see R2"), ("dev", "  padded  ")])
def test_handoff_args_that_check_out_pass(turn: str, note: str | None) -> None:
    require_valid_handoff_args(HANDOFF_CONFIG, task_id="tst-0001", turn=turn, note=note)


@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"turn": "dve"}, r"^'dve' is not a role; known: dev, reviewer, or human$"),
        ({"turn": "Human"}, r"^'Human' is not a role; known: dev, reviewer, or human$"),
        ({"turn": ""}, r"^'' is not a role; known: dev, reviewer, or human$"),
        ({"note": ""}, r"^--note is empty: give it text, or leave it out$"),
        ({"note": " \t "}, r"^--note is empty: give it text, or leave it out$"),
        ({"note": "one\ntwo"}, r"^--note holds a line break: give it one line$"),
        ({"note": "one\r"}, r"^--note holds a line break: give it one line$"),
        ({"note": "one\u2028two"}, r"^--note holds a line break: give it one line$"),
        ({"task_id": "TST-0001"}, r"^task id 'TST-0001' is not valid: "),
    ],
    ids=[
        "unknown-role",
        "human-capitalised",
        "empty-role",
        "empty-note",
        "blank-note",
        "note-newline",
        "note-return",
        "note-line-separator",
        "invalid-task-id",
    ],
)
def test_bad_handoff_args_are_refused_naming_the_problem(arguments, message) -> None:
    valid = {"task_id": "tst-0001", "turn": "dev", "note": None}
    with pytest.raises(FoundryError, match=message):
        require_valid_handoff_args(HANDOFF_CONFIG, **{**valid, **arguments})


def test_a_config_without_roles_knows_only_human() -> None:
    with pytest.raises(FoundryError, match=r"^'dev' is not a role; known: none, or human$"):
        require_valid_handoff_args(
            Config("f", {"store": Project("store", "url")}, {}), task_id="tst-0001", turn="dev", note=None
        )


@pytest.mark.parametrize(
    "turn, lines",
    [
        ("dev", ["task tst-0001 in store: handoff to dev", "run it with: foundry run store tst-0001"]),
        ("human", ["task tst-0001 in store: handoff to human"]),
    ],
)
def test_the_handoff_lines_say_how_to_run_the_task_unless_it_waits_for_you(turn: str, lines: list[str]) -> None:
    assert handoff_lines("store", "tst-0001", turn=turn) == lines


def test_handoff_takes_a_project_a_task_a_role_and_an_optional_note() -> None:
    args = cli.build_parser().parse_args(["task", "handoff", "store", "tst-0001", "dev", "--note", "see R2"])
    assert (args.project_name, args.task_id, args.turn, args.note) == ("store", "tst-0001", "dev", "see R2")
    assert cli.build_parser().parse_args(["task", "handoff", "store", "tst-0001", "human"]).note is None


def test_handoff_prints_where_the_task_went_or_an_error_and_exits_accordingly(
    project_repository, enter_foundry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, in a foundry of its own with one role, dev: its output and exit code, for a
    handoff and for each argument it refuses, which pushes nothing.

    The refusals are made on project gone, whose repository doesn't exist. An argument checked after the repository
    is read would fail with git's error instead."""
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/LOG.md": "# Log\n"})
    foundry_root = write_foundry(
        tmp_path / "foundry", {"store": project_repository.path, "gone": tmp_path / "gone.git"}, roles=["dev"]
    )
    enter_foundry(foundry_root)

    assert cli.main(["task", "handoff", "store", "tst-0000", "dev", "--note", "go"]) == 0
    assert capsys.readouterr() == (
        "task tst-0000 in store: handoff to dev\nrun it with: foundry run store tst-0000\n",
        "",
    )
    assert project_repository.notes_commits()[0] == "Handoff of task tst-0000 to dev"
    assert project_repository.notes_files()[".agent/tasks/open/tst-0000/LOG.md"].endswith("\nNote: go\n")

    notes_before = project_repository.notes_head()
    for arguments, error in [
        (["tst-0000", "planner"], "'planner' is not a role; known: dev, or human"),
        (["tst-0000", "dev", "--note", " "], "--note is empty: give it text, or leave it out"),
        (
            ["x", "dev"],
            "task id 'x' is not valid: use lowercase letters, '-', then four or more digits (e.g. wcf-0042)",
        ),
    ]:
        assert cli.main(["task", "handoff", "gone", *arguments]) == 1
        assert capsys.readouterr() == ("", f"error: {error}\n")
    assert cli.main(["task", "handoff", "store", "cls-0000", "dev"]) == 1
    assert capsys.readouterr() == ("", "error: task cls-0000 is closed\n")
    assert cli.main(["task", "handoff", "nope", "tst-0000", "dev"]) == 1
    assert capsys.readouterr() == ("", "error: unknown project 'nope'; known: gone, store\n")
    assert project_repository.notes_head() == notes_before


# --- foundry task show ------------------------------------------------------------------

LOG = "# Log\n\n## 1 · planner · planned\nDone.\n\n## 2 · dev · progress\nDone: a.\n\n- Asks D1 → human: b?\n \n\n"
LAST_ENTRY = "## 2 · dev · progress\nDone: a.\n\n- Asks D1 → human: b?"


@pytest.mark.parametrize(
    "turn_and_log, lines",
    [
        (TaskTurnAndLog(Task.as_open("tst-0000"), "human", LOG), ["turn: human", "", LAST_ENTRY]),
        (TaskTurnAndLog(Task.as_closed("cls-0000"), "dev", LOG), ["status: closed", "turn: dev", "", LAST_ENTRY]),
        (TaskTurnAndLog(Task.as_open("tst-0000"), "dev", "# Log\n"), ["turn: dev", "", "no log entry yet"]),
    ],
    ids=["open", "closed", "no-entry"],
)
def test_show_lines_are_the_status_if_closed_the_turn_a_blank_line_and_the_last_entry(
    turn_and_log: TaskTurnAndLog, lines: list[str]
) -> None:
    assert show_lines(turn_and_log) == lines


def test_show_takes_a_project_and_a_task() -> None:
    args = cli.build_parser().parse_args(["task", "show", "store", "tst-0001"])
    assert (args.project_name, args.task_id) == ("store", "tst-0001")


def test_task_help_lists_show(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["task", "--help"])
    assert "show" in capsys.readouterr().out.split("{", 1)[1].split("}", 1)[0].split(",")


def store_foundry(tmp_path: Path, project_repository: ProjectRepository, git_env: dict[str, str]) -> Path:
    """A foundry of its own, whose project store is ``project_repository``; gone, whose repository doesn't exist;
    and bare, whose repository has no branches."""
    bare_dir = tmp_path / "bare.git"
    git_output(git_env, "init", "--quiet", "--bare", str(bare_dir))
    return write_foundry(
        tmp_path / "foundry",
        {"store": project_repository.path, "gone": tmp_path / "gone.git", "bare": bare_dir},
    )


@pytest.mark.parametrize(
    "task_id, log, printed",
    [
        ("tst-0000", LOG, f"turn: dev\n\n{LAST_ENTRY}\n"),
        ("cls-0000", LOG, f"status: closed\nturn: dev\n\n{LAST_ENTRY}\n"),
        ("tst-0000", "# Log\n", "turn: dev\n\nno log entry yet\n"),
    ],
    ids=["open", "closed", "no-entry"],
)
def test_show_prints_the_turn_and_the_last_log_entry_and_exits_0(
    project_repository,
    enter_foundry,
    git_env,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    task_id,
    log,
    printed,
) -> None:
    found = project_repository.project_tasks().fetch_task(task_id)
    project_repository.edit_notes(write={found.turn_file: " dev \n", found.log_file: log})
    enter_foundry(store_foundry(tmp_path, project_repository, git_env))

    assert cli.main(["task", "show", "store", task_id]) == 0
    assert capsys.readouterr() == (printed, "")


TST_0000 = ".agent/tasks/open/tst-0000"
WELL_FORMED = {f"{TST_0000}/TURN": "dev\n", f"{TST_0000}/LOG.md": "# Log\n"}


@pytest.mark.parametrize(
    "project_name, task_id, write, symlink, error",
    [
        ("gone", "tst-0000", {}, {}, r"git -C \S+ ls-remote --heads origin failed: .*"),
        ("bare", "tst-0000", {}, {}, "the project repository has no agent-notes branch"),
        (
            "store",
            "tst-0009",
            {},
            {},
            "task tst-0009 doesn't exist: agent-notes has neither "
            r"\.agent/tasks/open/tst-0009/ nor \.agent/tasks/closed/tst-0009/",
        ),
        (
            "store",
            "tst-0000",
            {".agent/tasks/closed/tst-0000/TURN": "dev\n"},
            {},
            r"task tst-0000 is both open and closed: agent-notes has \.agent/tasks/open/tst-0000/ and "
            r"\.agent/tasks/closed/tst-0000/",
        ),
        (
            "store",
            "tst-0000",
            {f"{TST_0000}/LOG.md": "# Log\n"},
            {},
            r"task tst-0000 has no turn: agent-notes has no \.agent/tasks/open/tst-0000/TURN, or it is empty\.",
        ),
        (
            "store",
            "tst-0000",
            {f"{TST_0000}/TURN/x": "dev\n", f"{TST_0000}/LOG.md": "# Log\n"},
            {},
            r"task tst-0000 has no turn: agent-notes has no \.agent/tasks/open/tst-0000/TURN, or it is empty\.",
        ),
        (
            "store",
            "tst-0000",
            {f"{TST_0000}/TURN": " \n"},
            {},
            r"task tst-0000 has no turn: agent-notes has no \.agent/tasks/open/tst-0000/TURN, or it is empty\.",
        ),
        (
            "store",
            "tst-0000",
            {f"{TST_0000}/TURN": "dev\n"},
            {},
            r"task tst-0000 has no LOG\.md: agent-notes has no file \.agent/tasks/open/tst-0000/LOG\.md",
        ),
        (
            "store",
            "tst-0000",
            {f"{TST_0000}/TURN": "dev\n", f"{TST_0000}/LOG.md/x": "x\n"},
            {},
            r"task tst-0000 has no LOG\.md: agent-notes has no file \.agent/tasks/open/tst-0000/LOG\.md",
        ),
        (
            "store",
            "tst-0000",
            {f"{TST_0000}/LOG.md": "# Log\n"},
            {f"{TST_0000}/TURN": "/etc/hostname"},
            r"task tst-0000's TURN is a link, and foundry reads only files: "
            r"agent-notes has a link at \.agent/tasks/open/tst-0000/TURN",
        ),
        (
            "store",
            "tst-0000",
            {f"{TST_0000}/TURN": "dev\n", f"{TST_0000}/MARKER.md": "## 1 · dev · progress\nmarker-7f3a\n"},
            {f"{TST_0000}/LOG.md": "MARKER.md"},
            r"task tst-0000's LOG\.md is a link, and foundry reads only files: "
            r"agent-notes has a link at \.agent/tasks/open/tst-0000/LOG\.md",
        ),
    ],
    ids=[
        "unreachable",
        "no-agent-notes",
        "neither-open-nor-closed",
        "both-open-and-closed",
        "turn-missing",
        "turn-dir",
        "turn-blank",
        "log-missing",
        "log-dir",
        "turn-link",
        "log-link",
    ],
)
def test_show_fails_with_one_error_on_stderr_nothing_on_stdout_and_exits_1(
    project_repository,
    enter_foundry,
    git_env,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    project_name,
    task_id,
    write,
    symlink,
    error,
) -> None:
    """A link is never followed: neither its target's name nor its target's text is printed."""
    if write or symlink:
        project_repository.edit_notes(write=write, symlink=symlink)
    enter_foundry(store_foundry(tmp_path, project_repository, git_env))

    assert cli.main(["task", "show", project_name, task_id]) == 1
    printed = capsys.readouterr()
    assert printed.out == ""
    assert re.fullmatch(f"error: {error}\n", printed.err, flags=re.DOTALL), printed.err


@pytest.fixture
def enter_foundry_counting_git(
    enter_foundry, process_environment: ProcessEnvironment, tmp_path: Path
) -> Callable[[Path], Path]:
    """enter_foundry, with every git call counted: returns the file of recorded calls.

    The stand-in's dir goes first on PATH after enter_foundry, which replaces PATH."""

    def enter(foundry_root: Path) -> Path:
        enter_foundry(foundry_root)
        stand_in_dir = tmp_path / "counting"
        stand_in_dir.mkdir()
        git_calls = counting_stand_in(stand_in_dir, "git")
        process_environment.prepend_to_path(stand_in_dir)
        return git_calls

    return enter


@pytest.mark.parametrize(
    "project_name, task_id, error",
    [
        ("nope", "tst-0000", "unknown project 'nope'; known: bare, gone, store"),
        (
            "store",
            "x",
            "task id 'x' is not valid: use lowercase letters, '-', then four or more digits (e.g. wcf-0042)",
        ),
    ],
    ids=["unknown-project", "invalid-id"],
)
def test_show_refuses_an_unknown_project_or_an_invalid_id_before_running_git(
    project_repository,
    enter_foundry_counting_git,
    git_env,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    project_name,
    task_id,
    error,
) -> None:
    """test_show_only_reads_with_one_fetch shows the same setup records git when it runs."""
    git_calls = enter_foundry_counting_git(store_foundry(tmp_path, project_repository, git_env))

    assert cli.main(["task", "show", project_name, task_id]) == 1
    assert capsys.readouterr() == ("", f"error: {error}\n")
    assert not git_calls.exists()


def test_show_only_reads_with_one_fetch(
    project_repository,
    enter_foundry_counting_git,
    no_signing_key,
    git_env,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_repository.edit_notes(write=WELL_FORMED)
    refs_before = project_repository.git("for-each-ref")
    git_calls = enter_foundry_counting_git(store_foundry(tmp_path, project_repository, git_env))

    assert cli.main(["task", "show", "store", "tst-0000"]) == 0
    assert capsys.readouterr() == ("turn: dev\n\nno log entry yet\n", "")
    assert fetch_count(git_calls) == 1
    calls = [line.split() for line in git_calls.read_text().splitlines()]
    assert not [call for call in calls if "commit" in call or "push" in call]
    assert project_repository.git("for-each-ref") == refs_before
