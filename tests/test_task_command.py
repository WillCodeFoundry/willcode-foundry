"""foundry task create: its report, and its arguments."""

from pathlib import Path

from foundry import cli
from foundry.commands.task import report
from foundry.task import CreatedTask


def test_the_report_says_what_was_created_and_how_to_run_it() -> None:
    assert report("store", "T1", CreatedTask("task/T1", "main", ".agent/T1/TASK.md")) == [
        "created task T1 in store",
        "  branch   task/T1, from main",
        "  TASK.md  .agent/T1/TASK.md on agent-notes",
        "run it with: foundry run store ROLE T1",
    ]


def test_create_takes_a_project_a_task_and_a_file() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "T1", "T1.md"])
    assert (args.project_name, args.task_id, args.task_md_path) == ("store", "T1", Path("T1.md"))
