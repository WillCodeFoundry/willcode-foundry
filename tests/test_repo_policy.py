import copy
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from foundry import repo_policy
from foundry.errors import FoundryError
from foundry.github import GitHub, GitHubError

REPO_ROOT = Path(__file__).parents[1]
POLICY = repo_policy.load(REPO_ROOT / "config" / "repo-policy")

URL = "git@github.com:o/r.git"

RULESET: dict[str, Any] = {
    "name": "agent-branches",
    "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}],
    "conditions": {"ref_name": {"include": ["refs/heads/task/**", "refs/heads/agent-notes"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "pull_request", "parameters": {"required_approving_review_count": 1}}],
}


class FakeGitHub:
    """GitHub in memory, as foundry.github.GitHub describes it."""

    def __init__(self) -> None:
        self.stored_rulesets: dict[str, dict[str, dict[str, Any]]] = {}
        """Rulesets by repo slug, then by name; each stored with the id GitHub would give it."""
        self.files: dict[str, dict[str, str]] = {}
        """File text by repo slug, then path on the default branch."""
        self.unavailable: dict[str, str] = {}
        """Repo slug -> the message GitHub refuses it with, e.g. for a plan without rulesets."""
        self._next_id = 1

    def rulesets(self, repo_slug: str) -> dict[str, dict[str, Any]]:
        if repo_slug in self.unavailable:
            raise GitHubError(self.unavailable[repo_slug])
        return copy.deepcopy(self.stored_rulesets.get(repo_slug, {}))

    def file_text(self, *, repo_slug: str, file_path: str) -> str | None:
        return self.files.get(repo_slug, {}).get(file_path)

    def create_ruleset(self, repo_slug: str, ruleset: dict[str, Any]) -> None:
        self.stored_rulesets.setdefault(repo_slug, {})[ruleset["name"]] = {
            **copy.deepcopy(ruleset),
            "id": self._next_id,
        }
        self._next_id += 1

    def update_ruleset(self, repo_slug: str, ruleset_id: int, ruleset: dict[str, Any]) -> None:
        repo = self.stored_rulesets[repo_slug]
        (name,) = [name for name, stored in repo.items() if stored["id"] == ruleset_id]
        del repo[name]
        repo[ruleset["name"]] = {**copy.deepcopy(ruleset), "id": ruleset_id}

    def ruleset_id(self, repo_slug: str, ruleset_name: str) -> int:
        return int(self.stored_rulesets[repo_slug][ruleset_name]["id"])


_: type[GitHub] = FakeGitHub  # FakeGitHub implements the protocol


# A policy that is the real one but for its rulesets: just RULESET.
WITH_RULESET = dataclasses.replace(POLICY, rulesets=[RULESET])

# What this repository's own files make of the policy's files: a project that conforms.
CONFORMING_FILES = {
    path: (REPO_ROOT / path).read_text() for path in (repo_policy.CODEOWNERS_PATH, repo_policy.CI_WORKFLOW_PATH)
}


def conforming_to(policy: repo_policy.RepoPolicy = POLICY, repo_slug: str = "o/r") -> FakeGitHub:
    """A repository with exactly what the policy asks for: this repository's files, and the policy's rulesets."""
    fake = FakeGitHub()
    fake.files[repo_slug] = dict(CONFORMING_FILES)
    for ruleset in policy.rulesets:
        fake.create_ruleset(repo_slug, ruleset)
    return fake


def deviations(fake: FakeGitHub, policy: repo_policy.RepoPolicy = POLICY) -> list[repo_policy.Deviation]:
    """What check_project finds in the repository at URL; it must be checkable."""
    result = repo_policy.check_project(fake, URL, policy)
    assert result.error is None and result.changes == []
    return result.deviations


def with_ruleset(actual: dict[str, Any]) -> FakeGitHub:
    """A repository conforming to WITH_RULESET, but holding ``actual`` as GitHub returns it for agent-branches."""
    fake = conforming_to(WITH_RULESET)
    fake.stored_rulesets["o/r"]["agent-branches"] = {"id": 1, **actual}
    return fake


# --- how a ruleset compares ----------------------------------------------------------


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

    assert deviations(with_ruleset(actual), WITH_RULESET) == []


def test_extra_list_items_are_deviations() -> None:
    extra_actor = {**RULESET, "bypass_actors": [*RULESET["bypass_actors"], {"actor_type": "Team", "actor_id": 9}]}
    extra_rule = {**RULESET, "rules": [*RULESET["rules"], {"type": "creation"}]}

    for actual in (extra_actor, extra_rule):
        assert [d.subject for d in deviations(with_ruleset(actual), WITH_RULESET)] == ["ruleset agent-branches"]


def test_key_order_and_list_order_do_not_matter() -> None:
    reordered = {
        "rules": list(reversed(RULESET["rules"])),
        "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/agent-notes", "refs/heads/task/**"]}},
        "bypass_actors": RULESET["bypass_actors"],
        "name": "agent-branches",
    }

    assert deviations(with_ruleset(reordered), WITH_RULESET) == []


def test_a_deviation_reads_as_a_diff_from_actual_to_the_repo_policy() -> None:
    (deviation,) = deviations(with_ruleset({**RULESET, "rules": [{"type": "deletion"}]}), WITH_RULESET)

    assert deviation.subject == "ruleset agent-branches"
    assert deviation.diff.startswith("--- ruleset agent-branches (actual)\n+++ ruleset agent-branches (repo policy)\n")
    assert '+      "type": "pull_request"' in deviation.diff


def test_a_missing_ruleset_diffs_as_entirely_missing() -> None:
    fake = conforming_to(WITH_RULESET)
    fake.stored_rulesets["o/r"] = {}

    (deviation,) = deviations(fake, WITH_RULESET)

    assert deviation.diff.startswith("--- ruleset agent-branches (missing)\n")
    assert all(line.startswith(("+", "@", "---")) for line in deviation.diff.splitlines())


# --- how a project's files compare ------------------------------------------------


def codeowners_deviations(text: str | None) -> list[str]:
    """The subjects check_project reports for a conforming repository whose CODEOWNERS is ``text``, or absent."""
    fake = conforming_to()
    if text is None:
        del fake.files["o/r"][repo_policy.CODEOWNERS_PATH]
    else:
        fake.files["o/r"][repo_policy.CODEOWNERS_PATH] = text
    return [d.subject for d in deviations(fake)]


def test_text_deviates_only_beyond_trailing_whitespace() -> None:
    codeowners = POLICY.codeowners.rstrip("\n")

    assert codeowners_deviations(f"{codeowners}  \n\n\n") == []
    assert codeowners_deviations(codeowners) == []
    assert codeowners_deviations("* @someone\n") == [repo_policy.CODEOWNERS_PATH]
    assert codeowners_deviations(None) == [repo_policy.CODEOWNERS_PATH]


CI_GATE_TEXT = (REPO_ROOT / "config" / "repo-policy" / "ci-gate.yml").read_text()


def project_ci(*, needs: str, on: str | None = None) -> str:
    """A project's ci.yml as ci-gate.yml tells you to write one: jobs lint and test above ci-gate.

    ``on`` replaces the on: block when given. The text keeps ci-gate.yml's bare `on:` key, which
    YAML 1.1 reads as the boolean True.
    """
    assert CI_GATE_TEXT.count("jobs:\n") == 1 and CI_GATE_TEXT.count("needs: <all other jobs>") == 1
    text = CI_GATE_TEXT.replace("jobs:\n", "jobs:\n  lint: {}\n  test: {}\n").replace(
        "needs: <all other jobs>", f"needs: {needs}"
    )
    if on is not None:
        start, end = text.index("on:\n"), text.index("\njobs:")
        text = text[:start] + on + text[end:]
    return text


def ci_deviations(ci_text: str | None) -> list[repo_policy.Deviation]:
    """The deviations check_project reports for a conforming repository whose ci.yml is ``ci_text``, or absent."""
    fake = conforming_to()
    if ci_text is None:
        del fake.files["o/r"][repo_policy.CI_WORKFLOW_PATH]
    else:
        fake.files["o/r"][repo_policy.CI_WORKFLOW_PATH] = ci_text
    return deviations(fake)


def test_a_ci_gate_needing_every_other_job_conforms_whatever_the_jobs() -> None:
    """Read with its bare on: key, whose on: block matches the policy's."""
    assert ci_deviations(project_ci(needs="[test, lint]")) == []


def test_a_ci_gate_needing_too_few_jobs_deviates_and_the_diff_shows_them() -> None:
    (deviation,) = ci_deviations(project_ci(needs="[test]"))

    assert deviation.subject == repo_policy.CI_WORKFLOW_PATH
    assert any(line.startswith("-") and '"test"' in line for line in deviation.diff.splitlines())


def test_a_different_on_block_deviates() -> None:
    (deviation,) = ci_deviations(project_ci(needs="[test, lint]", on="on:\n  pull_request:\n"))

    assert deviation.subject == repo_policy.CI_WORKFLOW_PATH
    assert any(line.startswith("+") and '"workflow_dispatch"' in line for line in deviation.diff.splitlines())


@pytest.mark.parametrize("ci_text", [None, "on: [pull_request\n", "- a list\n"])
def test_a_projects_missing_or_broken_ci_yml_is_a_deviation_not_an_error(ci_text: str | None) -> None:
    (deviation,) = ci_deviations(ci_text)

    assert deviation.subject == repo_policy.CI_WORKFLOW_PATH
    assert deviation.diff.startswith(f"--- {repo_policy.CI_WORKFLOW_PATH} (missing)")


# --- check_project and fix_project ------------------------------------------------


def policy_with_rulesets(*rulesets: dict[str, Any]) -> repo_policy.RepoPolicy:
    return repo_policy.RepoPolicy(list(rulesets), codeowners="* @will\n", ci_gate={})


def test_fix_project_creates_the_missing_and_updates_the_deviating_in_policy_order() -> None:
    policy = dataclasses.replace(
        POLICY, rulesets=[{**RULESET, "name": "first"}, {**RULESET, "name": "second"}, {**RULESET, "name": "third"}]
    )
    fake = conforming_to(dataclasses.replace(POLICY, rulesets=[]))
    fake.create_ruleset("o/r", {**RULESET, "name": "second", "rules": [{"type": "deletion"}]})
    fake.create_ruleset("o/r", {**RULESET, "name": "third"})
    second_id = fake.ruleset_id("o/r", "second")

    result = repo_policy.fix_project(fake, URL, policy)

    assert result.changes == [
        repo_policy.RulesetChange("first", repo_policy.RulesetAction.CREATED),
        repo_policy.RulesetChange("second", repo_policy.RulesetAction.UPDATED),
    ]
    assert fake.ruleset_id("o/r", "second") == second_id  # updated in place, not recreated
    assert result.deviations == [] and result.conforms


def test_fix_project_leaves_a_matching_ruleset_alone() -> None:
    fake = conforming_to(WITH_RULESET)
    before = fake.rulesets("o/r")

    result = repo_policy.fix_project(fake, URL, WITH_RULESET)

    assert result == repo_policy.ProjectCheck([], [])
    assert fake.rulesets("o/r") == before


class FileReadFails(FakeGitHub):
    """GitHub that makes ruleset changes, then fails reading a file."""

    def file_text(self, *, repo_slug: str, file_path: str) -> str | None:
        raise GitHubError("Server Error (HTTP 502)")


def test_check_project_on_a_conforming_repository() -> None:
    result = repo_policy.check_project(conforming_to(), URL, POLICY)

    assert result == repo_policy.ProjectCheck([], []) and result.conforms


def test_check_project_lists_deviations_and_changes_nothing() -> None:
    fake = FakeGitHub()

    result = repo_policy.check_project(fake, URL, policy_with_rulesets(RULESET))

    assert result.changes == [] and result.error is None and not result.conforms
    assert [d.subject for d in result.deviations] == [
        "ruleset agent-branches",
        ".github/CODEOWNERS",
        ".github/workflows/ci.yml",
    ]
    assert fake.rulesets("o/r") == {}


def test_a_github_error_is_the_result_not_raised() -> None:
    fake = FakeGitHub()
    fake.unavailable["o/r"] = "Upgrade to GitHub Pro to use rulesets (HTTP 403)"

    for result in (repo_policy.check_project(fake, URL, POLICY), repo_policy.fix_project(fake, URL, POLICY)):
        assert result == repo_policy.ProjectCheck([], [], error="Upgrade to GitHub Pro to use rulesets (HTTP 403)")


def test_a_url_that_is_not_githubs_is_the_result_not_raised() -> None:
    url = "https://gitlab.com/o/p.git"

    for result in (
        repo_policy.check_project(FakeGitHub(), url, POLICY),
        repo_policy.fix_project(FakeGitHub(), url, POLICY),
    ):
        assert result.error == f"{url!r} is not a GitHub repository URL" and not result.conforms


def test_fix_project_creates_the_missing_rulesets_then_conforms() -> None:
    fake = conforming_to()
    fake.stored_rulesets["o/r"] = {}  # every ruleset missing

    result = repo_policy.fix_project(fake, URL, POLICY)

    assert result.changes == [
        repo_policy.RulesetChange(ruleset["name"], repo_policy.RulesetAction.CREATED) for ruleset in POLICY.rulesets
    ]
    assert result.deviations == [] and result.conforms


def test_fix_project_keeps_the_changes_made_before_github_failed() -> None:
    fake = FileReadFails()

    result = repo_policy.fix_project(fake, URL, policy_with_rulesets(RULESET))

    assert result == repo_policy.ProjectCheck(
        [repo_policy.RulesetChange("agent-branches", repo_policy.RulesetAction.CREATED)],
        [],
        error="Server Error (HTTP 502)",
    )
    assert "agent-branches" in fake.rulesets("o/r")


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
    assert deviations(conforming_to()) == []
