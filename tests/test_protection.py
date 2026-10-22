from pathlib import Path

import pytest

from foundry import protection
from foundry.errors import FoundryError
from foundry.github import GitHub
from foundry.protection import RulesetState
from tests.fake_github import FakeGitHub

REPO_ROOT = Path(__file__).parents[1]

RULESET = {
    "name": "agent-branches",
    "target": "branch",
    "enforcement": "active",
    "bypass_actors": [],
    "conditions": {"ref_name": {"include": ["refs/heads/task/**", "refs/heads/agent-notes"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
}


def test_the_shipped_protection_file_parses() -> None:
    rulesets = protection.load(REPO_ROOT / "config" / "github-protection.yaml")
    assert [ruleset["name"] for ruleset in rulesets] == [
        "foundry-default-branch",
        "foundry-agent-branches",
        "foundry-other-branches",
    ]
    admin_only = [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}]
    assert all(ruleset["bypass_actors"] == admin_only for ruleset in rulesets)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ([], "needs a 'rulesets' list"),
        ({"rulesets": [{"target": "branch"}]}, r"rulesets\[0\] needs a 'name'"),
        ({"rulesets": [{"name": "a"}, {"name": "a"}]}, "'a' is listed twice"),
    ],
)
def test_parse_refuses_bad_files(raw: object, message: str) -> None:
    with pytest.raises(FoundryError, match=message):
        protection.parse(raw)


def test_differences_ignores_fields_only_github_has() -> None:
    actual = {**RULESET, "id": 3, "node_id": "x", "rules": [*RULESET["rules"], {"type": "creation"}]}
    assert protection.differences(RULESET, actual) == []


def test_differences_matches_rules_by_type_and_lists_in_any_order() -> None:
    actual = {
        **RULESET,
        "conditions": {"ref_name": {"include": ["refs/heads/agent-notes", "refs/heads/task/**"], "exclude": []}},
        "rules": [{"type": "non_fast_forward"}, {"type": "deletion"}],
    }
    assert protection.differences(RULESET, actual) == []


def test_differences_names_each_shortfall() -> None:
    actual = {
        **RULESET,
        "enforcement": "evaluate",
        "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}],
        "rules": [{"type": "deletion"}],
    }
    assert protection.differences(RULESET, actual) == [
        "enforcement: expected 'active', found 'evaluate'",
        "bypass_actors: expected [], found [{'actor_type': 'RepositoryRole', 'actor_id': 5, 'bypass_mode': 'always'}]",
        "rules[non_fast_forward]: missing",
    ]


def test_differences_compares_rule_parameters() -> None:
    desired = {"rules": [{"type": "pull_request", "parameters": {"required_approving_review_count": 1}}]}
    actual = {"rules": [{"type": "pull_request", "parameters": {"required_approving_review_count": 0, "other": 1}}]}
    assert protection.differences(desired, actual) == [
        "rules[pull_request].parameters.required_approving_review_count: expected 1, found 0"
    ]


def test_check_repo_reports_each_state_and_leaves_unmanaged_rulesets_alone() -> None:
    fake = FakeGitHub()
    fake.add("o/r", RULESET)
    fake.add("o/r", {**RULESET, "name": "drifted", "enforcement": "disabled"})
    fake.add("o/r", {**RULESET, "name": "someone-elses"})
    fake.add("o/r", {**RULESET, "name": "from-the-org"}, source_type="Organization")
    wanted = [RULESET, {**RULESET, "name": "drifted"}, {**RULESET, "name": "absent"}]

    status = protection.check_repo(GitHub(fake), "o/r", wanted)

    assert [(s.ruleset_name, s.state) for s in status.rulesets] == [
        ("agent-branches", RulesetState.OK),
        ("drifted", RulesetState.DIFFERS),
        ("absent", RulesetState.MISSING),
    ]
    assert status.rulesets[1].differences == ["enforcement: expected 'active', found 'disabled'"]
    assert status.unmanaged_ruleset_names == ["someone-elses"]
    assert not status.is_protected


def test_apply_status_creates_and_updates_until_the_repo_is_protected() -> None:
    fake = FakeGitHub()
    fake.add("o/r", {**RULESET, "enforcement": "disabled"})
    wanted = [RULESET, {**RULESET, "name": "absent"}]
    github = GitHub(fake)

    for status in protection.check_repo(github, "o/r", wanted).rulesets:
        protection.apply_status(github, "o/r", status)

    assert protection.check_repo(github, "o/r", wanted).is_protected
    assert ("PUT", "repos/o/r/rulesets/1") in fake.calls
    assert ("POST", "repos/o/r/rulesets") in fake.calls


GATED: protection.Ruleset = {
    "name": "default-branch",
    "rules": [
        {"type": "pull_request", "parameters": {"require_code_owner_review": True}},
        {
            "type": "required_status_checks",
            "parameters": {"required_status_checks": [{"context": "ci-gate", "integration_id": 15368}]},
        },
    ],
}
GATE_WORKFLOW = "on: pull_request\njobs:\n  test: {}\n  ci-gate: {needs: [test]}\n"


def file_checks(files: dict[str, str], rulesets: list[protection.Ruleset]) -> list[tuple[str, bool, str]]:
    fake = FakeGitHub()
    fake.files["o/r"] = files
    return [(c.description, c.ok, c.detail) for c in protection.check_project_files(GitHub(fake), "o/r", rulesets)]


def test_project_files_that_support_the_rules() -> None:
    files = {".github/workflows/ci.yml": GATE_WORKFLOW, ".github/CODEOWNERS": ".github/ @will\n"}
    assert file_checks(files, [GATED]) == [
        ("required check ci-gate", True, ".github/workflows/ci.yml"),
        ("CODEOWNERS", True, ".github/CODEOWNERS owns the workflows and itself"),
    ]


def test_a_project_without_the_gate_job_or_codeowners() -> None:
    files = {".github/workflows/ci.yml": "on: pull_request\njobs:\n  test: {}\n", "README.md": ""}
    assert file_checks(files, [GATED]) == [
        ("required check ci-gate", False, "no workflow on the default branch runs a job of that name on pull requests"),
        ("CODEOWNERS", False, "no CODEOWNERS file, but code owner review is required"),
    ]


def test_codeowners_must_own_the_workflows_and_itself() -> None:
    files = {".github/workflows/ci.yml": GATE_WORKFLOW, "CODEOWNERS": "/src/ @will\n"}
    assert file_checks(files, [GATED])[1] == ("CODEOWNERS", False, "no owner for .github/workflows/ci.yml, CODEOWNERS")


def test_a_project_with_no_workflows_at_all() -> None:
    assert file_checks({"CODEOWNERS": "* @will\n"}, [GATED])[0][1] is False


def test_project_files_are_not_read_when_no_rule_needs_them() -> None:
    fake = FakeGitHub()
    assert protection.check_project_files(GitHub(fake), "o/r", [RULESET]) == []
    assert fake.calls == []


def test_the_shipped_file_requires_the_ci_gate_and_code_owner_review() -> None:
    rulesets = protection.load(REPO_ROOT / "config" / "github-protection.yaml")
    assert protection.required_check_names(rulesets) == ["ci-gate"]
    assert protection.requires_code_owner_review(rulesets)
