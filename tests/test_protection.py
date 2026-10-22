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
        "foundry-tags",
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
GATE_WORKFLOW = "on: pull_request\njobs:\n  test: {}\n  ci-gate: {if: always(), needs: [test]}\n"


def file_checks(
    files: dict[str, str], rulesets: list[protection.Ruleset], permissions: dict[str, str] | None = None
) -> list[tuple[str, bool, str]]:
    fake = FakeGitHub()
    fake.files["o/r"] = files
    fake.permissions["o/r"] = {"will": "admin", **(permissions or {})}
    return [(c.description, c.ok, c.detail) for c in protection.check_project_files(GitHub(fake), "o/r", rulesets)]


def codeowners_check(codeowners: str, permissions: dict[str, str] | None = None) -> tuple[bool, str]:
    files = {".github/workflows/ci.yml": GATE_WORKFLOW, ".github/CODEOWNERS": codeowners}
    _, ok, detail = file_checks(files, [GATED], permissions)[1]
    return ok, detail


def test_project_files_that_support_the_rules() -> None:
    files = {".github/workflows/ci.yml": GATE_WORKFLOW, ".github/CODEOWNERS": "* @will\n"}
    assert file_checks(files, [GATED]) == [
        ("required check ci-gate", True, ".github/workflows/ci.yml"),
        ("CODEOWNERS", True, ".github/CODEOWNERS: admins own every file"),
    ]


def test_a_project_without_the_gate_job_or_codeowners() -> None:
    files = {".github/workflows/ci.yml": "on: pull_request\njobs:\n  test: {}\n", "README.md": ""}
    assert file_checks(files, [GATED]) == [
        ("required check ci-gate", False, "no workflow on the default branch runs a job of that name on pull requests"),
        ("CODEOWNERS", False, "no CODEOWNERS file, but code owner review is required"),
    ]


def test_owning_only_github_is_not_enough() -> None:
    # A pull request that leaves .github/ alone would need one approval from
    # anyone with write access, such as the reviewer role.
    ok, detail = codeowners_check(".github/ @will\n")
    assert not ok and "no catch-all line" in detail


def test_a_line_that_unowns_files_is_refused() -> None:
    ok, detail = codeowners_check("* @will\n/src/generated/\n")
    assert not ok and "lines that leave files without an owner: /src/generated/" in detail


def test_owners_must_be_admins() -> None:
    ok, detail = codeowners_check("* @will\n/src/ @reviewer-bot\n/docs/ @stranger\n", {"reviewer-bot": "write"})
    assert not ok
    assert "@reviewer-bot has write access, not admin" in detail
    assert "@stranger has none access, not admin" in detail


def test_team_and_email_owners_cannot_be_checked() -> None:
    ok, detail = codeowners_check("* @will @org/devs a@b.c\n")
    assert not ok
    assert "@org/devs can't be checked" in detail and "a@b.c can't be checked" in detail


def test_a_project_with_no_workflows_at_all() -> None:
    assert file_checks({"CODEOWNERS": "* @will\n"}, [GATED])[0][1] is False


def test_project_files_are_not_read_when_no_rule_needs_them() -> None:
    fake = FakeGitHub()
    assert protection.check_project_files(GitHub(fake), "o/r", [RULESET]) == []
    assert fake.calls == []


def test_the_shipped_file_leaves_dependabot_its_branches_and_closes_tags() -> None:
    rulesets = {
        ruleset["name"]: ruleset for ruleset in protection.load(REPO_ROOT / "config" / "github-protection.yaml")
    }
    other_branches = rulesets["foundry-other-branches"]["conditions"]["ref_name"]
    assert "refs/heads/dependabot/**" in other_branches["exclude"]
    tags = rulesets["foundry-tags"]
    assert tags["target"] == "tag" and tags["conditions"]["ref_name"]["include"] == ["~ALL"]
    assert {rule["type"] for rule in tags["rules"]} == {"creation", "update", "deletion"}


def test_the_shipped_file_requires_the_ci_gate_and_code_owner_review() -> None:
    rulesets = protection.load(REPO_ROOT / "config" / "github-protection.yaml")
    assert protection.required_check_names(rulesets) == ["ci-gate"]
    assert protection.requires_code_owner_review(rulesets)


def test_differences_ignore_key_order_and_github_fields_inside_list_items() -> None:
    desired = {"bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}]}
    # The order GitHub's documented response uses, plus a field it may add.
    actual = {"bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always", "x": 1}]}
    assert protection.differences(desired, actual) == []


def test_differences_still_catch_an_extra_or_changed_list_item() -> None:
    desired = {"bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5}]}
    extra = {"bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole"}, {"actor_id": 4, "actor_type": "Team"}]}
    changed = {"bypass_actors": [{"actor_id": 4, "actor_type": "RepositoryRole"}]}
    assert protection.differences(desired, extra) != []
    assert protection.differences(desired, changed) != []
    assert protection.differences({"include": ["a", "a"]}, {"include": ["a", "b"]}) != []


def gate_check(workflow: str, default_branch: str = "main") -> tuple[bool, str]:
    fake = FakeGitHub()
    fake.files["o/r"] = {".github/workflows/ci.yml": workflow}
    fake.default_branches["o/r"] = default_branch
    gate_only = {"name": "g", "rules": [GATED["rules"][1]]}
    (check,) = protection.check_project_files(GitHub(fake), "o/r", [gate_only])
    return check.ok, check.detail


@pytest.mark.parametrize(
    "on",
    [
        "pull_request",
        "{pull_request: {branches: [main]}}",
        "{pull_request: {branches: ['**']}}",
        "{pull_request: {branches: ['ma*', '!release/*']}}",
        "{pull_request: {types: [opened, synchronize]}}",
    ],
)
def test_triggers_that_always_run_on_pull_requests_into_main(on: str) -> None:
    assert gate_check(f"on: {on}\njobs:\n  ci-gate: {{}}\n") == (True, ".github/workflows/ci.yml")


@pytest.mark.parametrize(
    ("on", "problem"),
    [
        ("{pull_request: {paths: ['src/**']}}", "has a paths filter"),
        ("{pull_request: {paths-ignore: ['docs/**']}}", "has a paths-ignore filter"),
        ("{pull_request: {branches-ignore: [wip]}}", "has a branches-ignore filter"),
        ("{pull_request: {branches: [develop]}}", "branches filter leaves out main"),
        ("{pull_request: {branches: ['**', '!main']}}", "branches filter leaves out main"),
    ],
)
def test_triggers_that_can_leave_pull_requests_without_the_check(on: str, problem: str) -> None:
    ok, detail = gate_check(f"on: {on}\njobs:\n  ci-gate: {{}}\n")
    assert not ok and problem in detail


def test_the_branch_filter_is_matched_against_the_actual_default_branch() -> None:
    assert gate_check("on: {pull_request: {branches: [trunk]}}\njobs:\n  ci-gate: {}\n", "trunk")[0]


@pytest.mark.parametrize(
    ("job", "problem"),
    [
        ("{if: \"github.event_name == 'push'\"}", "has if: github.event_name == 'push'; when it skips"),
        ("{if: success(), needs: [test]}", "has if: success()"),
        ("{needs: [test]}", "needs other jobs but has no if: always()"),
    ],
)
def test_a_gate_that_can_be_skipped_counts_as_passed_and_is_refused(job: str, problem: str) -> None:
    ok, detail = gate_check(f"on: pull_request\njobs:\n  test: {{}}\n  ci-gate: {job}\n")
    assert not ok and problem in detail


def test_always_is_accepted_in_either_spelling() -> None:
    for condition in ("always()", "${{ always() }}"):
        assert gate_check(f"on: pull_request\njobs:\n  t: {{}}\n  ci-gate: {{if: '{condition}', needs: [t]}}\n")[0]
