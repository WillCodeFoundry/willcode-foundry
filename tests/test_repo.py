"""foundry repo check: its report, and its arguments."""

from foundry import cli
from foundry.commands.repo import report
from foundry.repo_policy import Deviation, RulesetAction, RulesetChange


def test_a_conforming_repository() -> None:
    assert report("store", "o/store", [], []) == ["store (o/store)", "  conforms"]


def test_what_fix_changed_comes_before_the_result() -> None:
    changes = [
        RulesetChange("agent-branches", RulesetAction.CREATED),
        RulesetChange("tags", RulesetAction.UPDATED),
    ]
    assert report("store", "o/store", changes, []) == [
        "store (o/store)",
        "  created  ruleset agent-branches",
        "  updated  ruleset tags",
        "  conforms",
    ]


def test_each_deviation_with_its_diff_indented() -> None:
    deviation = Deviation(".github/CODEOWNERS", "--- a\n+++ b\n-* @someone\n+* @will\n")
    assert report("store", "o/store", [], [deviation]) == [
        "store (o/store)",
        "  differs  .github/CODEOWNERS",
        "           --- a",
        "           +++ b",
        "           -* @someone",
        "           +* @will",
    ]


def test_fix_and_project_names_parse() -> None:
    args = cli.build_parser().parse_args(["repo", "check", "--fix", "store"])
    assert (args.fix, args.project_names) == (True, ["store"])
    assert cli.build_parser().parse_args(["repo", "check"]).fix is False
