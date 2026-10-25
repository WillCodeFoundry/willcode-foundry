"""foundry repo check: check_one_project against FakeGitHub, its report, and its arguments."""

from pathlib import Path

import pytest

from foundry import cli, config, repo_policy
from foundry.commands.repo import CheckedProject, check_one_project, report
from foundry.errors import FoundryError
from foundry.repo_policy import Deviation, ProjectCheck, RulesetAction, RulesetChange
from tests.fakes import FakeGitHub

REPO_ROOT = Path(__file__).parents[1]
POLICY = repo_policy.load(REPO_ROOT / "config" / "repo-policy")
CONFIG = config.parse(
    {
        "name": "test",
        "projects": {
            "store": {"url": "git@github.com:o/store.git"},
        },
        "roles": {},
    }
)


def conforming(fake: FakeGitHub, repo_slug: str) -> None:
    """Give the repository exactly what the policy asks for, as this repository has it."""
    for path in (repo_policy.CODEOWNERS_PATH, repo_policy.CI_WORKFLOW_PATH):
        fake.files.setdefault(repo_slug, {})[path] = (REPO_ROOT / path).read_text()
    for ruleset in POLICY.rulesets:
        fake.create_ruleset(repo_slug, ruleset)


def check(fake: FakeGitHub, project_name: str, *, fix: bool = False, foundry_config: config.Config = CONFIG):
    """The project's printed lines, and whether it conforms."""
    project = check_one_project(foundry_config, POLICY, fake, project_name, fix=fix)
    return report(project), project.result.conforms


# --- check_one_project ----------------------------------------------------------


def test_a_conforming_project() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")

    assert check(fake, "store") == (["store (o/store)", "  conforms"], True)


def test_a_deviating_project() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")
    fake.files["o/store"][repo_policy.CODEOWNERS_PATH] = "* @someone\n"

    lines, conforms = check(fake, "store")

    assert lines[:2] == ["store (o/store)", "  differs  .github/CODEOWNERS"] and not conforms


def test_a_project_github_refuses_is_reported_not_raised() -> None:
    fake = FakeGitHub()
    fake.unavailable["o/store"] = "Upgrade to GitHub Pro to use rulesets (HTTP 403)"

    assert check(fake, "store") == (
        ["store (o/store)", "  error    Upgrade to GitHub Pro to use rulesets (HTTP 403)"],
        False,
    )


def test_fix_creates_the_missing_rulesets_reports_them_then_conforms() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")
    fake.stored_rulesets["o/store"] = {}  # every ruleset missing

    assert check(fake, "store", fix=True) == (
        [
            "store (o/store)",
            *[f"  created  ruleset {ruleset['name']}" for ruleset in POLICY.rulesets],
            "  conforms",
        ],
        True,
    )


def test_an_unknown_project_name_is_refused() -> None:
    with pytest.raises(FoundryError, match="unknown project 'nope'"):
        check(FakeGitHub(), "nope")


def test_a_project_whose_url_is_not_githubs_is_reported_not_raised() -> None:
    foundry_config = config.parse(
        {"name": "test", "projects": {"elsewhere": {"url": "https://gitlab.com/o/p.git"}}, "roles": {}}
    )

    assert check(FakeGitHub(), "elsewhere", foundry_config=foundry_config) == (
        ["elsewhere", "  error    'https://gitlab.com/o/p.git' is not a GitHub repository URL"],
        False,
    )


# --- report ---------------------------------------------------------------------


def test_a_conforming_repository() -> None:
    assert report(CheckedProject("store", "o/store", ProjectCheck([], []))) == ["store (o/store)", "  conforms"]


def test_what_fix_changed_comes_before_the_result() -> None:
    changes = [
        RulesetChange("agent-branches", RulesetAction.CREATED),
        RulesetChange("tags", RulesetAction.UPDATED),
    ]
    assert report(CheckedProject("store", "o/store", ProjectCheck(changes, []))) == [
        "store (o/store)",
        "  created  ruleset agent-branches",
        "  updated  ruleset tags",
        "  conforms",
    ]


def test_each_deviation_with_its_diff_indented() -> None:
    deviation = Deviation(".github/CODEOWNERS", "--- a\n+++ b\n-* @someone\n+* @will\n")
    assert report(CheckedProject("store", "o/store", ProjectCheck([], [deviation]))) == [
        "store (o/store)",
        "  differs  .github/CODEOWNERS",
        "           --- a",
        "           +++ b",
        "           -* @someone",
        "           +* @will",
    ]


def test_an_error_follows_the_changes_made_before_it() -> None:
    changes = [RulesetChange("agent-branches", RulesetAction.CREATED)]
    assert report(CheckedProject("store", "o/store", ProjectCheck(changes, [], error="boom (HTTP 502)"))) == [
        "store (o/store)",
        "  created  ruleset agent-branches",
        "  error    boom (HTTP 502)",
    ]


# --- arguments ------------------------------------------------------------------


def test_fix_and_project_names_parse() -> None:
    args = cli.build_parser().parse_args(["repo", "check", "--fix", "store"])
    assert (args.fix, args.project_names) == (True, ["store"])
    assert cli.build_parser().parse_args(["repo", "check"]).fix is False
