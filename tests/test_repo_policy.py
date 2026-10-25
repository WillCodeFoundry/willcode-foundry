from pathlib import Path
from typing import Any

import pytest
import yaml

from foundry import repo_policy
from foundry.errors import FoundryError
from foundry.github import GitHubError
from tests.fakes import FakeGitHub

REPO_ROOT = Path(__file__).parents[1]
POLICY = repo_policy.load(REPO_ROOT / "config" / "repo-policy")

RULESET: dict[str, Any] = {
    "name": "agent-branches",
    "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}],
    "conditions": {"ref_name": {"include": ["refs/heads/task/**", "refs/heads/agent-notes"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "pull_request", "parameters": {"required_approving_review_count": 1}}],
}


def conforms(actual: object, expected: object) -> bool:
    return repo_policy.compare("x", repo_policy.restrict_to(expected, actual), expected) is None


# --- restriction and comparison -------------------------------------------------


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
    assert conforms(actual, RULESET)


def test_extra_list_items_are_deviations() -> None:
    extra_actor = {**RULESET, "bypass_actors": [*RULESET["bypass_actors"], {"actor_type": "Team", "actor_id": 9}]}
    extra_rule = {**RULESET, "rules": [*RULESET["rules"], {"type": "creation"}]}
    assert not conforms(extra_actor, RULESET)
    assert not conforms(extra_rule, RULESET)


def test_key_order_and_list_order_do_not_matter() -> None:
    reordered = {
        "rules": list(reversed(RULESET["rules"])),
        "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/agent-notes", "refs/heads/task/**"]}},
        "bypass_actors": RULESET["bypass_actors"],
        "name": "agent-branches",
    }
    assert conforms(reordered, RULESET)


def test_a_deviation_reads_as_a_diff_from_actual_to_the_repo_policy() -> None:
    actual = {**RULESET, "rules": [{"type": "deletion"}]}
    deviation = repo_policy.compare("ruleset agent-branches", repo_policy.restrict_to(RULESET, actual), RULESET)
    assert deviation is not None and deviation.subject == "ruleset agent-branches"
    assert deviation.diff.startswith("--- ruleset agent-branches (actual)\n+++ ruleset agent-branches (repo policy)\n")
    assert '+      "type": "pull_request"' in deviation.diff


def test_a_missing_ruleset_diffs_as_entirely_missing() -> None:
    deviation = repo_policy.compare("ruleset r", None, RULESET)
    assert deviation is not None and deviation.diff.startswith("--- ruleset r (missing)\n")
    assert all(line.startswith(("+", "@", "---")) for line in deviation.diff.splitlines())


def test_text_deviates_only_beyond_trailing_whitespace() -> None:
    assert repo_policy.compare("CODEOWNERS", "* @will  \n\n\n", "* @will\n") is None
    assert repo_policy.compare("CODEOWNERS", "* @will", "* @will\n") is None
    assert repo_policy.compare("CODEOWNERS", "* @someone\n", "* @will\n") is not None
    assert repo_policy.compare("CODEOWNERS", None, "* @will\n") is not None


# --- the ci-gate section of ci.yml ------------------------------------------------

CI = yaml.safe_load("""\
on:
  pull_request:
jobs:
  lint: {}
  test: {}
  ci-gate:
    if: always()
    needs: [test, lint]
""")


def test_needs_naming_every_other_job_becomes_the_placeholder() -> None:
    assert repo_policy.ci_gate_section(CI)["jobs"]["ci-gate"]["needs"] == repo_policy.ALL_OTHER_JOBS


def test_needs_missing_a_job_is_left_as_it_is_so_the_diff_shows_it() -> None:
    workflow = {**CI, "jobs": {**CI["jobs"], "ci-gate": {**CI["jobs"]["ci-gate"], "needs": ["test"]}}}
    assert repo_policy.ci_gate_section(workflow)["jobs"]["ci-gate"]["needs"] == ["test"]


def test_a_bare_on_key_is_read_as_on() -> None:
    assert True in CI  # what YAML 1.1 makes of `on:`
    assert repo_policy.ci_gate_section(CI)["on"] == {"pull_request": None}


@pytest.mark.parametrize("ci_text", [None, "on: [pull_request\n", "- a list\n"])
def test_a_projects_missing_or_broken_ci_yml_is_a_deviation_not_an_error(ci_text: str | None) -> None:
    fake = FakeGitHub()
    if ci_text is not None:
        fake.files["o/r"] = {repo_policy.CI_WORKFLOW_PATH: ci_text}
    deviation = repo_policy.deviations(fake, "o/r", POLICY)[-1]
    assert deviation.subject == repo_policy.CI_WORKFLOW_PATH
    assert deviation.diff.startswith(f"--- {repo_policy.CI_WORKFLOW_PATH} (missing)")


# --- apply_rulesets ------------------------------------------------------------------


def policy_of(*rulesets: dict[str, Any]) -> repo_policy.RepoPolicy:
    return repo_policy.RepoPolicy(list(rulesets), codeowners="* @will\n", ci_gate={})


def test_apply_rulesets_creates_the_missing_and_updates_the_deviating_in_policy_order() -> None:
    fake = FakeGitHub()
    fake.create_ruleset("o/r", {**RULESET, "name": "second", "rules": [{"type": "deletion"}]})
    fake.create_ruleset("o/r", {**RULESET, "name": "third"})
    second_id = fake.ruleset_id("o/r", "second")
    policy = policy_of({**RULESET, "name": "first"}, {**RULESET, "name": "second"}, {**RULESET, "name": "third"})

    changes = list(repo_policy.apply_rulesets(fake, "o/r", policy))

    assert changes == [
        repo_policy.RulesetChange("first", repo_policy.RulesetAction.CREATED),
        repo_policy.RulesetChange("second", repo_policy.RulesetAction.UPDATED),
    ]
    assert fake.ruleset_id("o/r", "second") == second_id  # updated in place, not recreated
    assert [d.subject for d in repo_policy.deviations(fake, "o/r", policy) if d.subject.startswith("ruleset")] == []


def test_apply_rulesets_leaves_a_matching_ruleset_alone() -> None:
    fake = FakeGitHub()
    fake.create_ruleset("o/r", RULESET)
    before = fake.rulesets("o/r")

    assert list(repo_policy.apply_rulesets(fake, "o/r", policy_of(RULESET))) == []
    assert fake.rulesets("o/r") == before


class FileReadFails(FakeGitHub):
    """GitHub that makes ruleset changes, then fails reading a file."""

    def file_text(self, repo_slug: str, file_path: str) -> str | None:
        raise GitHubError("Server Error (HTTP 502)")


def test_check_project_keeps_the_changes_fix_made_before_github_failed() -> None:
    fake = FileReadFails()

    result = repo_policy.check_project(fake, "o/r", policy_of(RULESET), fix=True)

    assert result == repo_policy.ProjectCheck(
        [repo_policy.RulesetChange("agent-branches", repo_policy.RulesetAction.CREATED)],
        [],
        error="Server Error (HTTP 502)",
    )
    assert not result.conforms
    assert "agent-branches" in fake.rulesets("o/r")


def test_check_project_without_fix_changes_nothing() -> None:
    fake = FakeGitHub()

    result = repo_policy.check_project(fake, "o/r", policy_of(RULESET), fix=False)

    assert result.changes == [] and result.error is None
    assert [d.subject for d in result.deviations] == [
        "ruleset agent-branches",
        ".github/CODEOWNERS",
        ".github/workflows/ci.yml",
    ]
    assert fake.rulesets("o/r") == {}


# --- loading the policy -------------------------------------------------------------


@pytest.fixture
def policy_dir(tmp_path: Path) -> Path:
    """A readable repo policy, for each test to break one file of."""
    (tmp_path / "rulesets.yaml").write_text("rulesets: []\n")
    (tmp_path / "ci-gate.yml").write_text("on: pull_request\njobs: {}\n")
    (tmp_path / "CODEOWNERS").write_text("* @will\n")
    repo_policy.load(tmp_path)
    return tmp_path


@pytest.mark.parametrize("content", ["- a list\n", "rulesets: none\n", "other: []\n"])
def test_a_rulesets_yaml_without_a_rulesets_list_is_named(policy_dir: Path, content: str) -> None:
    (policy_dir / "rulesets.yaml").write_text(content)
    with pytest.raises(FoundryError, match=rf"^{policy_dir / 'rulesets.yaml'}: needs a 'rulesets' list$"):
        repo_policy.load(policy_dir)


def test_a_ci_gate_yml_foundry_cannot_read_is_named(policy_dir: Path) -> None:
    (policy_dir / "ci-gate.yml").write_text("- a list\n")
    with pytest.raises(FoundryError, match=rf"^{policy_dir / 'ci-gate.yml'}: not a workflow fragment foundry can read"):
        repo_policy.load(policy_dir)


def test_a_missing_codeowners_is_named(policy_dir: Path) -> None:
    (policy_dir / "CODEOWNERS").unlink()
    with pytest.raises(FoundryError, match=rf"^{policy_dir / 'CODEOWNERS'} is missing$"):
        repo_policy.load(policy_dir)


# --- this repository --------------------------------------------------------------


def test_this_repository_conforms_to_its_own_repo_policy() -> None:
    """The foundry is one of its own projects: its CODEOWNERS and ci.yml keep the policy honest."""
    fake = FakeGitHub()
    for path in (repo_policy.CODEOWNERS_PATH, repo_policy.CI_WORKFLOW_PATH):
        fake.files.setdefault("o/r", {})[path] = (REPO_ROOT / path).read_text()
    for ruleset in POLICY.rulesets:
        fake.create_ruleset("o/r", ruleset)

    assert repo_policy.deviations(fake, "o/r", POLICY) == []
