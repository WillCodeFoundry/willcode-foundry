from pathlib import Path
from typing import Any

from foundry import standard
from foundry.github import GitHub
from tests.fake_github import FakeGitHub

REPO_ROOT = Path(__file__).parents[1]
STANDARD = standard.load(REPO_ROOT / "config" / "project-standard")

RULESET: dict[str, Any] = {
    "name": "agent-branches",
    "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}],
    "conditions": {"ref_name": {"include": ["refs/heads/task/**", "refs/heads/agent-notes"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "pull_request", "parameters": {"required_approving_review_count": 1}}],
}


def matches(actual: object, template: object) -> bool:
    return not standard.compare("x", standard.project(actual, template), template).diff


# --- projection and comparison ------------------------------------------------


def test_fields_github_adds_are_ignored() -> None:
    actual = {
        **RULESET,
        "id": 7,
        "source_type": "Repository",
        "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
        "rules": [
            {"type": "deletion"},
            {"type": "pull_request", "parameters": {"required_approving_review_count": 1, "allowed_merge_methods": []}},
        ],
    }
    assert matches(actual, RULESET)


def test_extra_list_items_are_reported() -> None:
    extra_actor = {**RULESET, "bypass_actors": [*RULESET["bypass_actors"], {"actor_type": "Team", "actor_id": 9}]}
    extra_rule = {**RULESET, "rules": [*RULESET["rules"], {"type": "creation"}]}
    assert not matches(extra_actor, RULESET)
    assert not matches(extra_rule, RULESET)


def test_key_order_and_list_order_do_not_matter() -> None:
    reordered = {
        "rules": list(reversed(RULESET["rules"])),
        "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/agent-notes", "refs/heads/task/**"]}},
        "bypass_actors": RULESET["bypass_actors"],
        "name": "agent-branches",
    }
    assert matches(reordered, RULESET)


def test_a_difference_reads_as_a_diff_from_actual_to_standard() -> None:
    actual = {**RULESET, "rules": [{"type": "deletion"}]}
    diff = standard.compare("ruleset agent-branches", standard.project(actual, RULESET), RULESET).diff
    assert diff.startswith("--- ruleset agent-branches (actual)\n+++ ruleset agent-branches (standard)\n")
    assert '+      "type": "pull_request"' in diff


def test_a_missing_ruleset_diffs_as_entirely_missing() -> None:
    diff = standard.compare("ruleset r", None, RULESET).diff
    assert diff.startswith("--- ruleset r (missing)\n")
    assert all(line.startswith(("+", "@", "---")) for line in diff.splitlines())


def test_text_differs_only_beyond_trailing_whitespace() -> None:
    assert not standard.compare("CODEOWNERS", "* @will  \n\n\n", "* @will\n").diff
    assert not standard.compare("CODEOWNERS", "* @will", "* @will\n").diff
    assert standard.compare("CODEOWNERS", "* @someone\n", "* @will\n").diff
    assert standard.compare("CODEOWNERS", None, "* @will\n").diff


# --- the ci.yml fragment ------------------------------------------------------

CI = """\
on:
  pull_request:
jobs:
  lint: {}
  test: {}
  ci-gate:
    if: always()
    needs: [test, lint]
"""


def test_needs_naming_every_other_job_becomes_the_placeholder() -> None:
    gate = standard.fragment(CI)
    assert gate is not None
    assert gate["jobs"]["ci-gate"]["needs"] == standard.ALL_OTHER_JOBS


def test_needs_missing_a_job_is_left_as_it_is_so_the_diff_shows_it() -> None:
    gate = standard.fragment(CI.replace("needs: [test, lint]", "needs: [test]"))
    assert gate is not None
    assert gate["jobs"]["ci-gate"]["needs"] == ["test"]


def test_a_bare_on_key_is_read_as_on() -> None:
    gate = standard.fragment(CI)
    assert gate is not None
    assert gate["on"] == {"pull_request": None}


def test_a_missing_or_unreadable_ci_yml_has_no_fragment() -> None:
    assert standard.fragment("on: [pull_request\n") is None
    assert standard.fragment("- a list\n") is None
    finding = standard.check(GitHub(FakeGitHub()), "o/r", STANDARD)[-1]
    assert finding.subject == standard.CI_PATH and finding.diff.startswith(f"--- {standard.CI_PATH} (missing)")


# --- the standard itself --------------------------------------------------------


def test_this_repository_meets_its_own_standard() -> None:
    """The foundry is one of its own projects: its CODEOWNERS and ci.yml keep the template honest."""
    fake = FakeGitHub()
    for path in (standard.CODEOWNERS_PATH, standard.CI_PATH):
        fake.files.setdefault("o/r", {})[path] = (REPO_ROOT / path).read_text()
    for ruleset in STANDARD.rulesets:
        fake.add("o/r", ruleset)

    findings = standard.check(GitHub(fake), "o/r", STANDARD)

    assert [finding.diff for finding in findings] == [""] * len(findings)
