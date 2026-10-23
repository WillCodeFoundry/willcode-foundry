"""foundry/task.py against a fake GitHub, and the `foundry task create` command's report and arguments."""

from pathlib import Path

import pytest

from foundry import cli, task
from foundry.commands.task import report
from foundry.errors import FoundryError
from tests.fakes import FakeGitHub

TEMPLATE = {"TASK.md": "# Task <id>: <title>\n", "PROGRESS.md": "# Progress\n"}
TASK_FILES = {".agent/T1/TASK.md": "# Task <id>: <title>\n", ".agent/T1/PROGRESS.md": "# Progress\n"}


@pytest.fixture
def github() -> FakeGitHub:
    github = FakeGitHub()
    github.branches["o/r"] = {"main": "base-sha", task.AGENT_NOTES_BRANCH: "notes-sha"}
    github.branch_files["o/r"] = {task.AGENT_NOTES_BRANCH: {".agent/T0/TASK.md": "an earlier task\n"}}
    return github


# --- create ---------------------------------------------------------------------


def test_a_task_is_its_branch_from_the_default_branch_and_the_template_in_its_notes_folder(github) -> None:
    task.create(github, "o/r", "T1", TEMPLATE)

    assert github.branch_head("o/r", "task/T1") == "base-sha"
    assert github.branch_files["o/r"][task.AGENT_NOTES_BRANCH] == {
        ".agent/T0/TASK.md": "an earlier task\n",
        **TASK_FILES,
    }


def test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files(github) -> None:
    del github.branches["o/r"][task.AGENT_NOTES_BRANCH]
    del github.branch_files["o/r"]

    task.create(github, "o/r", "T1", TEMPLATE)

    assert github.branch_files["o/r"][task.AGENT_NOTES_BRANCH] == TASK_FILES


def test_an_existing_task_branch_is_refused(github) -> None:
    github.branches["o/r"]["task/T1"] = "old-sha"

    with pytest.raises(FoundryError, match="task T1 already exists"):
        task.create(github, "o/r", "T1", TEMPLATE)
    assert ".agent/T1/TASK.md" not in github.branch_files["o/r"][task.AGENT_NOTES_BRANCH]


def test_an_existing_notes_file_is_refused_and_kept(github) -> None:
    github.branch_files["o/r"][task.AGENT_NOTES_BRANCH][".agent/T1/PROGRESS.md"] = "theirs\n"

    with pytest.raises(FoundryError, match="task T1 already exists"):
        task.create(github, "o/r", "T1", TEMPLATE)
    assert "task/T1" not in github.branches["o/r"]
    assert github.file_text("o/r", ".agent/T1/PROGRESS.md", task.AGENT_NOTES_BRANCH) == "theirs\n"


def test_an_invalid_task_id_is_refused(github) -> None:
    with pytest.raises(FoundryError, match="task id 'bad id' is not valid"):
        task.create(github, "o/r", "bad id", TEMPLATE)


def test_a_repository_with_no_commits_is_refused(github) -> None:
    del github.branches["o/r"]["main"]

    with pytest.raises(FoundryError, match="no commits on main"):
        task.create(github, "o/r", "T1", TEMPLATE)


# --- load_template ----------------------------------------------------------------


def test_the_template_is_every_file_directly_in_its_folder(tmp_path: Path) -> None:
    (tmp_path / "TASK.md").write_text("# Task\n")
    (tmp_path / "PROGRESS.md").write_text("# Progress\n")
    (tmp_path / "drafts").mkdir()
    (tmp_path / "drafts" / "ignored.md").write_text("no\n")

    assert task.load_template(tmp_path) == {"PROGRESS.md": "# Progress\n", "TASK.md": "# Task\n"}


def test_a_missing_template_folder_is_named(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match=r"task-template is missing$"):
        task.load_template(tmp_path / "task-template")


# --- the command ------------------------------------------------------------------


def test_the_report_says_what_was_created_and_how_to_run_it() -> None:
    assert report("store", "T1") == ["created task T1 in store", "run it with: foundry run store ROLE T1"]


def test_create_takes_a_project_and_a_task() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "T1"])
    assert (args.project_name, args.task_id) == ("store", "T1")
