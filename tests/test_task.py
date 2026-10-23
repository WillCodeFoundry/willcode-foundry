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
    github.branches["o/r"] = {"main": "base-sha", task.AGENT_NOTES_BRANCH: "notes-sha"}
    return github


def test_a_task_is_its_branch_from_the_default_branch_and_its_task_md_on_agent_notes(github) -> None:
    task.create(github, "o/r", "T1", TASK_MD)

    assert github.branch_head("o/r", "task/T1") == "base-sha"
    assert github.file_text("o/r", ".agent/T1/TASK.md", task.AGENT_NOTES_BRANCH) == TASK_MD


def test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_task_md(github) -> None:
    del github.branches["o/r"][task.AGENT_NOTES_BRANCH]

    task.create(github, "o/r", "T1", TASK_MD)

    assert github.branch_files["o/r"][task.AGENT_NOTES_BRANCH] == {".agent/T1/TASK.md": TASK_MD}
    assert github.branch_head("o/r", "task/T1") == "base-sha"


def test_an_existing_task_branch_is_refused(github) -> None:
    github.branches["o/r"]["task/T1"] = "old-sha"

    with pytest.raises(FoundryError, match="task T1 already exists"):
        task.create(github, "o/r", "T1", TASK_MD)
    assert github.file_text("o/r", ".agent/T1/TASK.md", task.AGENT_NOTES_BRANCH) is None


def test_an_existing_task_md_is_refused_and_kept(github) -> None:
    github.branch_files["o/r"] = {task.AGENT_NOTES_BRANCH: {".agent/T1/TASK.md": "theirs\n"}}

    with pytest.raises(FoundryError, match="task T1 already exists"):
        task.create(github, "o/r", "T1", TASK_MD)
    assert "task/T1" not in github.branches["o/r"]
    assert github.file_text("o/r", ".agent/T1/TASK.md", task.AGENT_NOTES_BRANCH) == "theirs\n"


def test_an_invalid_task_id_is_refused(github) -> None:
    with pytest.raises(FoundryError, match="task id 'bad id' is not valid"):
        task.create(github, "o/r", "bad id", TASK_MD)


def test_a_repository_with_no_commits_is_refused(github) -> None:
    del github.branches["o/r"]["main"]

    with pytest.raises(FoundryError, match="no commits on main"):
        task.create(github, "o/r", "T1", TASK_MD)


# --- the command ------------------------------------------------------------------


def test_the_report_says_what_was_created_and_how_to_run_it() -> None:
    assert report("store", "T1") == ["created task T1 in store", "run it with: foundry run store ROLE T1"]


def test_create_takes_a_project_a_task_and_a_file() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "T1", "T1.md"])
    assert (args.project_name, args.task_id, args.task_md_path) == ("store", "T1", Path("T1.md"))
