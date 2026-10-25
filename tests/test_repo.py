"""foundry repo check: its report, and its arguments."""

from foundry import cli
from foundry.commands.repo import report
from foundry.config import Project
from foundry.repo_policy import Deviation, ProjectCheck, RulesetAction, RulesetChange

STORE = Project(name="store", url="git@github.com:o/store.git")


# --- report ---------------------------------------------------------------------


def test_a_conforming_repository() -> None:
    assert report(STORE, ProjectCheck([], [])) == ["store (o/store)", "  conforms"]


def test_what_fix_changed_comes_before_the_result() -> None:
    changes = [
        RulesetChange("agent-branches", RulesetAction.CREATED),
        RulesetChange("tags", RulesetAction.UPDATED),
    ]
    assert report(STORE, ProjectCheck(changes, [])) == [
        "store (o/store)",
        "  created  ruleset agent-branches",
        "  updated  ruleset tags",
        "  conforms",
    ]


def test_each_deviation_with_its_diff_indented() -> None:
    deviation = Deviation(subject=".github/CODEOWNERS", diff="--- a\n+++ b\n-* @someone\n+* @will\n")
    assert report(STORE, ProjectCheck([], [deviation])) == [
        "store (o/store)",
        "  differs  .github/CODEOWNERS",
        "           --- a",
        "           +++ b",
        "           -* @someone",
        "           +* @will",
    ]


def test_an_error_follows_the_changes_made_before_it() -> None:
    changes = [RulesetChange("agent-branches", RulesetAction.CREATED)]
    assert report(STORE, ProjectCheck(changes, [], error="boom (HTTP 502)")) == [
        "store (o/store)",
        "  created  ruleset agent-branches",
        "  error    boom (HTTP 502)",
    ]


# --- arguments ------------------------------------------------------------------


def test_fix_and_project_names_parse() -> None:
    args = cli.build_parser().parse_args(["repo", "check", "--fix", "store"])
    assert (args.fix, args.project_names) == (True, ["store"])
    assert cli.build_parser().parse_args(["repo", "check"]).fix is False


def test_a_project_whose_url_is_not_githubs_has_no_repo_in_its_header() -> None:
    elsewhere = Project(name="elsewhere", url="https://gitlab.com/o/p.git")
    assert report(elsewhere, ProjectCheck([], [], error="not GitHub")) == ["elsewhere", "  error    not GitHub"]
