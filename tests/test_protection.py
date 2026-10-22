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
    assert all(ruleset["bypass_actors"] == [] for ruleset in rulesets)


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
