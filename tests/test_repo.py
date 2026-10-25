"""foundry repo check: check_projects against FakeGitHub, its report, and its arguments."""

from pathlib import Path

import pytest

from foundry import cli, config, repo_policy
from foundry.commands.repo import check_projects, report
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
            "bench": {"url": "git@github.com:o/bench.git"},
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


def check(fake: FakeGitHub, *project_names: str, fix: bool = False, foundry_config: config.Config = CONFIG):
    lines: list[str] = []
    exit_code = check_projects(foundry_config, POLICY, fake, list(project_names), fix=fix, emit=lines.append)
    return exit_code, lines


# --- check_projects -------------------------------------------------------------


def test_every_project_conforming_exits_0_reporting_each_in_name_order() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")
    conforming(fake, "o/bench")

    assert check(fake) == (0, ["bench (o/bench)", "  conforms", "store (o/store)", "  conforms"])


def test_one_deviating_project_exits_1_and_the_others_are_still_reported() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")
    conforming(fake, "o/bench")
    fake.files["o/bench"][repo_policy.CODEOWNERS_PATH] = "* @someone\n"

    exit_code, lines = check(fake)

    assert exit_code == 1
    assert lines[:2] == ["bench (o/bench)", "  differs  .github/CODEOWNERS"]
    assert lines[-2:] == ["store (o/store)", "  conforms"]


def test_a_project_github_refuses_is_reported_and_the_rest_are_still_checked() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")
    fake.unavailable["o/bench"] = "Upgrade to GitHub Pro to use rulesets (HTTP 403)"

    assert check(fake) == (
        1,
        [
            "bench (o/bench)",
            "  error    Upgrade to GitHub Pro to use rulesets (HTTP 403)",
            "store (o/store)",
            "  conforms",
        ],
    )


def test_fix_creates_the_missing_rulesets_reports_them_then_conforms() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")
    fake.stored_rulesets["o/store"] = {}  # every ruleset missing

    exit_code, lines = check(fake, "store", fix=True)

    assert exit_code == 0
    assert lines == [
        "store (o/store)",
        *[f"  created  ruleset {ruleset['name']}" for ruleset in POLICY.rulesets],
        "  conforms",
    ]


def test_only_the_named_projects_are_checked() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")

    assert check(fake, "store") == (0, ["store (o/store)", "  conforms"])


def test_an_unknown_project_name_is_refused() -> None:
    with pytest.raises(FoundryError, match="unknown project 'nope'"):
        check(FakeGitHub(), "nope")


def test_a_project_whose_url_is_not_githubs_is_reported_and_the_rest_are_still_checked() -> None:
    fake = FakeGitHub()
    conforming(fake, "o/store")
    foundry_config = config.parse(
        {
            "name": "test",
            "projects": {
                "elsewhere": {"url": "https://gitlab.com/o/p.git"},
                "store": {"url": "git@github.com:o/store.git"},
            },
            "roles": {},
        }
    )

    exit_code, lines = check(fake, foundry_config=foundry_config)

    assert exit_code == 1
    assert lines[0] == "elsewhere"
    assert lines[1].startswith("  error    ") and "is not a GitHub repository URL" in lines[1]
    assert lines[2:] == ["store (o/store)", "  conforms"]


# --- report ---------------------------------------------------------------------


def test_a_conforming_repository() -> None:
    assert report(ProjectCheck([], [])) == ["  conforms"]


def test_what_fix_changed_comes_before_the_result() -> None:
    changes = [
        RulesetChange("agent-branches", RulesetAction.CREATED),
        RulesetChange("tags", RulesetAction.UPDATED),
    ]
    assert report(ProjectCheck(changes, [])) == [
        "  created  ruleset agent-branches",
        "  updated  ruleset tags",
        "  conforms",
    ]


def test_each_deviation_with_its_diff_indented() -> None:
    deviation = Deviation(".github/CODEOWNERS", "--- a\n+++ b\n-* @someone\n+* @will\n")
    assert report(ProjectCheck([], [deviation])) == [
        "  differs  .github/CODEOWNERS",
        "           --- a",
        "           +++ b",
        "           -* @someone",
        "           +* @will",
    ]


def test_an_error_follows_the_changes_made_before_it() -> None:
    changes = [RulesetChange("agent-branches", RulesetAction.CREATED)]
    assert report(ProjectCheck(changes, [], error="boom (HTTP 502)")) == [
        "  created  ruleset agent-branches",
        "  error    boom (HTTP 502)",
    ]


# --- arguments ------------------------------------------------------------------


def test_fix_and_project_names_parse() -> None:
    args = cli.build_parser().parse_args(["repo", "check", "--fix", "store"])
    assert (args.fix, args.project_names) == (True, ["store"])
    assert cli.build_parser().parse_args(["repo", "check"]).fix is False
