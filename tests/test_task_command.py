"""The `foundry task` commands: their reports, arguments and checks, and end to end through cli.main."""

import os
import sys
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
)
from foundry.config import Config, Project, Role
from foundry.errors import FoundryError
from foundry.project_tasks import TaskTurn
from foundry.task import CLOSED_DIR, OPEN_DIR, Task
from tests.support.foundry_root import write_foundry
from tests.support.machine import scripted_stand_in
from tests.support.project_repository import git_output

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


def test_create_s_task_is_optional_and_its_help_says_what_is_picked_without_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.build_parser().parse_args(["task", "create", "store"]).task_id is None

    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["task", "create", "--help"])
    usage = " ".join(capsys.readouterr().out.split())
    assert "PROJECT [TASK]" in usage
    assert (
        "task id, e.g. wcf-0042 (default: the next id with the task prefix most of the project's task ids use; "
        "ids with other task prefixes are ignored)" in usage
    )


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


# --- foundry task create without TASK ---------------------------------------------------------


@pytest.fixture
def foundry_of_store(project_repository, enter_foundry, tmp_path: Path) -> Path:
    """A foundry of its own, entered, with project store and a task template holding one TASK.md."""
    foundry_root = write_foundry(tmp_path / "foundry", {"store": project_repository.path})
    (foundry_root / "config" / "task-template").mkdir()
    (foundry_root / "config" / "task-template" / "TASK.md").write_text("# Task\n")
    enter_foundry(foundry_root)
    return foundry_root


def test_create_without_a_task_creates_the_next_one(
    project_repository, foundry_of_store, capsys: pytest.CaptureFixture[str]
) -> None:
    project_repository.edit_notes(
        write={f"{OPEN_DIR}/wcf-0030/TASK.md": "x\n", f"{CLOSED_DIR}/wcf-0032/TASK.md": "x\n"},
        remove=project_repository.seeded_task_notes_dirs,
    )
    project_repository.git("branch", "task/wcf-0033", "main")

    assert cli.main(["task", "create", "store"]) == 0

    assert capsys.readouterr() == ("created task wcf-0034 in store\nrun it with: foundry run store wcf-0034\n", "")
    assert project_repository.head("task/wcf-0034") == project_repository.head("main")
    assert project_repository.notes_files()[f"{OPEN_DIR}/wcf-0034/TASK.md"] == "# Task\n"


def take_no_task_id(project_repository) -> None:
    project_repository.git("branch", "--quiet", "-D", "agent-notes")


def tie_two_task_prefixes(project_repository) -> None:
    project_repository.edit_notes(
        write={f"{CLOSED_DIR}/wcf-0002/TASK.md": "x\n"}, remove=project_repository.seeded_task_notes_dirs
    )
    project_repository.git("branch", "task/abc-0001", "main")


@pytest.mark.parametrize(
    "take_task_ids, error",
    [
        (take_no_task_id, "the project repository has no task id to follow"),
        (tie_two_task_prefixes, "the project repository's task ids tie for the most common task prefix: abc, wcf"),
    ],
    ids=["no-task-id", "tie"],
)
def test_create_without_a_task_that_can_t_pick_one_says_to_give_it_and_changes_nothing(
    project_repository, foundry_of_store, capsys: pytest.CaptureFixture[str], take_task_ids, error: str
) -> None:
    take_task_ids(project_repository)
    refs_before = project_repository.git("for-each-ref")

    assert cli.main(["task", "create", "store"]) == 1

    assert capsys.readouterr() == ("", f"error: {error}. Give TASK to say which task to create.\n")
    assert project_repository.git("for-each-ref") == refs_before


def test_a_create_that_loses_the_race_for_its_id_fails_and_leaves_only_the_winner_s(
    project_repository, foundry_of_store, process_environment, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both creates pick wcf-0031. A git stand-in runs the competing create just before this one's push.

    The competitor commits at another date: two creates in the same second, by the same identity, make the same
    commit, and the second push changes nothing."""
    project_repository.edit_notes(
        write={f"{OPEN_DIR}/wcf-0030/TASK.md": "x\n"}, remove=project_repository.seeded_task_notes_dirs
    )
    notes_before = project_repository.notes_head()
    bin_dir, tips = tmp_path / "bin", tmp_path / "winner-tips"
    bin_dir.mkdir()
    real_path = os.environ["PATH"]  # git_env's, as enter_foundry set it
    scripted_stand_in(
        bin_dir,
        "git",
        f"""case " $* " in *" push "*)
  if [ ! -e {tips} ]; then
    PATH={real_path} GIT_COMMITTER_DATE=2001-01-01T00:00:00Z {sys.executable} -m foundry.cli task create store \
      >/dev/null 2>&1
    git --git-dir={project_repository.path} rev-parse agent-notes task/wcf-0031 > {tips}
  fi ;;
esac
PATH={real_path} exec git "$@"
""",
    )
    process_environment.set_env({"PATH": f"{bin_dir}:{real_path}"})

    assert cli.main(["task", "create", "store"]) == 1

    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("error: ")
    winner_notes, winner_branch = tips.read_text().split()
    assert project_repository.git("rev-parse", f"{project_repository.notes_head()}^") == notes_before
    assert (project_repository.notes_head(), project_repository.head("task/wcf-0031")) == (winner_notes, winner_branch)
    assert project_repository.git("for-each-ref", "--format=%(refname)", "refs/heads/task/").splitlines() == [
        "refs/heads/task/wcf-0031"
    ]
    assert [path for path in project_repository.notes_files() if "wcf-0031" in path] == [f"{OPEN_DIR}/wcf-0031/TASK.md"]


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
