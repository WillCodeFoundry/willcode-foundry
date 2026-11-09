"""foundry/task.py: Task and its ids, and the task template."""

from pathlib import Path

import pytest

from foundry import task
from foundry.errors import FoundryError
from foundry.task import Status, Task

# --- Task -----------------------------------------------------------------------


def test_an_open_task_is_its_id_its_branch_and_its_task_notes_dir_under_open() -> None:
    a_task = Task.as_open("wcf-0042")
    assert (a_task.id, a_task.branch, a_task.task_notes_dir, a_task.task_file, a_task.turn_file, a_task.log_file) == (
        "wcf-0042",
        "task/wcf-0042",
        ".agent/tasks/open/wcf-0042",
        ".agent/tasks/open/wcf-0042/TASK.md",
        ".agent/tasks/open/wcf-0042/TURN",
        ".agent/tasks/open/wcf-0042/LOG.md",
    )
    assert a_task == Task("wcf-0042", Status.OPEN)


def test_a_closed_task_s_task_notes_dir_is_under_closed() -> None:
    a_task = Task.as_closed("wcf-0042")
    assert (a_task.branch, a_task.task_notes_dir, a_task.task_file, a_task.turn_file) == (
        "task/wcf-0042",
        ".agent/tasks/closed/wcf-0042",
        ".agent/tasks/closed/wcf-0042/TASK.md",
        ".agent/tasks/closed/wcf-0042/TURN",
    )


@pytest.mark.parametrize("task_id", ["wcf-0042", "a-0000", "wcf-10000"])
@pytest.mark.parametrize("build", [Task.as_open, Task.as_closed, lambda task_id: Task(task_id, Status.OPEN)])
def test_valid_task_ids_are_kept_as_given(build, task_id: str) -> None:
    assert build(task_id).id == task_id


# U+212A, the Kelvin sign, lowercases to an ASCII k.
KELVIN = "\u212a"


@pytest.mark.parametrize(
    "task_id",
    [
        "WCF-0042",
        "Wcf-0042",
        "wcf-042",
        "wcf0042",
        "wcf-",
        "-0042",
        "w2-0042",
        "wcf_0042",
        "wcf-0042.lock",
        "fix-login.2",
        "t1",
        "7",
        f"{KELVIN}cf-0042",
        "",
        "wcf-0042\n",
        "wcf-\u0664\u0662\u0660\u0660",  # Arabic-Indic digits
    ],
)
@pytest.mark.parametrize("build", [Task.as_open, Task.as_closed, lambda task_id: Task(task_id, Status.OPEN)])
def test_task_ids_not_matching_the_pattern_are_refused_as_given(build, task_id: str) -> None:
    with pytest.raises(FoundryError) as error:
        build(task_id)
    assert str(error.value) == (
        f"task id {task_id!r} is not valid: use lowercase letters, '-', then four or more digits (e.g. wcf-0042)"
    )


# --- next_task_id ----------------------------------------------------------------


@pytest.mark.parametrize(
    "taken_ids, next_id",
    [
        (["wcf-0041"], "wcf-0042"),
        (["wcf-9999"], "wcf-10000"),
        (["wcf-00041"], "wcf-0042"),
        (["wcf-0001", "wcf-0005"], "wcf-0006"),  # gaps are never reused
    ],
)
def test_the_next_task_id_is_one_more_than_the_highest_padded_to_four_digits(taken_ids, next_id: str) -> None:
    assert task.next_task_id(taken_ids) == next_id


def test_names_that_aren_t_task_ids_are_ignored() -> None:
    assert task.next_task_id(["wcf-0005", "spike", "WCF-0099"]) == "wcf-0006"


def test_the_most_common_task_prefix_wins_and_the_other_task_prefix_s_higher_number_is_ignored() -> None:
    assert task.next_task_id(["wcf-0001", "wcf-0002", "sbx-0050"]) == "wcf-0003"


def test_each_id_is_counted_once() -> None:
    assert task.next_task_id(["wcf-0001", "wcf-0001", "wcf-0001", "sbx-0050", "sbx-0051"]) == "sbx-0052"


@pytest.mark.parametrize(
    "taken_ids, message",
    [
        ([], "the project repository has no task id to follow"),
        (["spike"], "the project repository has no task id to follow"),
        (
            ["abc-0001", "wcf-0002"],
            "the project repository's task ids tie for the most common task prefix: abc, wcf",
        ),
        (
            ["abc-0001", "wcf-0002", "xyz-0003", "xyz-0004", "wcf-0005"],
            "the project repository's task ids tie for the most common task prefix: wcf, xyz",
        ),
    ],
    ids=["none", "none-valid", "tie", "tie-of-two-of-three"],
)
def test_no_next_task_id_when_none_is_taken_or_task_prefixes_tie(taken_ids, message: str) -> None:
    with pytest.raises(task.NoNextTaskIdError) as error:
        task.next_task_id(taken_ids)
    assert str(error.value) == message


# --- load_task_template ----------------------------------------------------------------


def test_the_task_template_is_every_file_directly_in_its_dir(tmp_path: Path) -> None:
    (tmp_path / "TASK.md").write_text("# Task\n")
    (tmp_path / "PROGRESS.md").write_text("# Progress\n")
    (tmp_path / "drafts").mkdir()
    (tmp_path / "drafts" / "ignored.md").write_text("no\n")

    assert task.load_task_template(tmp_path) == {"PROGRESS.md": "# Progress\n", "TASK.md": "# Task\n"}


def test_a_template_without_a_task_md_is_refused(tmp_path: Path) -> None:
    task_template_dir = tmp_path / "task-template"
    task_template_dir.mkdir()
    (task_template_dir / "PROGRESS.md").write_text("# Progress\n")

    with pytest.raises(FoundryError, match=r"task-template has no TASK\.md; every task needs one$"):
        task.load_task_template(task_template_dir)


def test_a_missing_task_template_dir_is_named(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match=r"task-template is missing$"):
        task.load_task_template(tmp_path / "task-template")


def test_the_task_template_starts_with_the_planner_s_turn() -> None:
    template = task.load_task_template(Path(__file__).parents[1] / "config" / "task-template")
    assert template[task.TURN_FILE].strip() == "planner"
