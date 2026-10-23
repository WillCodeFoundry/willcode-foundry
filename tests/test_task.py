"""foundry/task.py against a fake GitHub, and the `foundry task create` command's report and arguments."""

from pathlib import Path

import pytest

from foundry import cli, task
from foundry.commands.task import report
from foundry.errors import FoundryError
from tests.fakes import FakeGitHub

TASK_MD = "# Task T1: refunds\n"


@pytest.fixture
def github() -> FakeGitHub:
    github = FakeGitHub()
    github.branches["o/r"] = {"main": "base-sha", task.NOTES_BRANCH: "notes-sha"}
    return github


# --- agent-notes ----------------------------------------------------------------


def test_ensure_notes_branch_creates_it_with_no_history_and_only_a_readme() -> None:
    github = FakeGitHub()

    assert task.ensure_notes_branch(github, "o/r") is True
    assert task.has_notes_branch(github, "o/r")
    assert list(github.branch_files["o/r"][task.NOTES_BRANCH]) == [".agent/README.md"]


def test_ensure_notes_branch_leaves_an_existing_one_alone(github) -> None:
    assert task.ensure_notes_branch(github, "o/r") is False
    assert github.branch_head("o/r", task.NOTES_BRANCH) == "notes-sha"


# --- create ---------------------------------------------------------------------


def test_a_task_is_its_branch_from_the_default_branch_and_its_task_md_on_agent_notes(github) -> None:
    created = task.create(github, "o/r", "T1", TASK_MD)

    assert created == task.CreatedTask("task/T1", "main", ".agent/T1/TASK.md")
    assert github.branch_head("o/r", "task/T1") == "base-sha"
    assert github.file_text("o/r", ".agent/T1/TASK.md", task.NOTES_BRANCH) == TASK_MD


def test_a_repository_without_agent_notes_is_refused(github) -> None:
    del github.branches["o/r"][task.NOTES_BRANCH]

    with pytest.raises(FoundryError, match="no agent-notes branch; `foundry repo check --fix` creates it"):
        task.create(github, "o/r", "T1", TASK_MD)
    assert "task/T1" not in github.branches["o/r"]


def test_an_existing_task_branch_is_refused(github) -> None:
    github.branches["o/r"]["task/T1"] = "old-sha"

    with pytest.raises(FoundryError, match="task T1 already exists"):
        task.create(github, "o/r", "T1", TASK_MD)
    assert github.file_text("o/r", ".agent/T1/TASK.md", task.NOTES_BRANCH) is None


def test_an_existing_task_md_is_refused_and_kept(github) -> None:
    github.branch_files["o/r"] = {task.NOTES_BRANCH: {".agent/T1/TASK.md": "theirs\n"}}

    with pytest.raises(FoundryError, match="task T1 already exists"):
        task.create(github, "o/r", "T1", TASK_MD)
    assert "task/T1" not in github.branches["o/r"]
    assert github.file_text("o/r", ".agent/T1/TASK.md", task.NOTES_BRANCH) == "theirs\n"


def test_an_invalid_task_id_is_refused(github) -> None:
    with pytest.raises(FoundryError, match="task id 'bad id' is not valid"):
        task.create(github, "o/r", "bad id", TASK_MD)


def test_a_repository_with_no_commits_is_refused(github) -> None:
    del github.branches["o/r"]["main"]

    with pytest.raises(FoundryError, match="no commits on main"):
        task.create(github, "o/r", "T1", TASK_MD)


# --- the command ------------------------------------------------------------------


def test_the_report_says_what_was_created_and_how_to_run_it() -> None:
    assert report("store", "T1", task.CreatedTask("task/T1", "main", ".agent/T1/TASK.md")) == [
        "created task T1 in store",
        "  branch   task/T1, from main",
        "  TASK.md  .agent/T1/TASK.md on agent-notes",
        "run it with: foundry run store ROLE T1",
    ]


def test_create_takes_a_project_a_task_and_a_file() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "T1", "T1.md"])
    assert (args.project_name, args.task_id, args.task_md_path) == ("store", "T1", Path("T1.md"))
