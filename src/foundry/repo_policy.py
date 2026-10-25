"""The repo policy: what every project's GitHub repository must match.

config/repo-policy/ holds the rulesets, the CODEOWNERS file and the ci-gate
section of ci.yml (when it runs, and its ci-gate job) that the rulesets
depend on. A repository is checked by comparing it with these, not by
analysing what it has: anything different is a deviation, even when
harmless. When a project really needs to differ, change the policy.
"""

import difflib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from foundry import yaml_io
from foundry.errors import FoundryError
from foundry.github import GitHub, repo_slug_from_url

CODEOWNERS_PATH = ".github/CODEOWNERS"
CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
CI_GATE_JOB = "ci-gate"
ALL_OTHER_JOBS = "<all other jobs>"


@dataclass(frozen=True)
class RepoPolicy:
    rulesets: list[dict[str, Any]]
    codeowners: str
    ci_gate: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class Deviation:
    """One way a repository differs from the repo policy, as a diff from it to the policy."""

    subject: str
    diff: str


class RulesetAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"


@dataclass(frozen=True)
class RulesetChange:
    """One ruleset apply_rulesets created or updated."""

    ruleset_name: str
    action: RulesetAction


def load(policy_dir: Path) -> RepoPolicy:
    """Read config/repo-policy/; a file that's missing or not what foundry expects fails with its path."""
    rulesets_path = policy_dir / "rulesets.yaml"
    rulesets_document = yaml_io.load(rulesets_path)
    if not isinstance(rulesets_document, dict) or not isinstance(rulesets_document.get("rulesets"), list):
        raise FoundryError(f"{rulesets_path}: needs a 'rulesets' list")

    ci_gate_path = policy_dir / "ci-gate.yml"
    try:
        ci_gate = ci_gate_section(yaml_io.load(ci_gate_path))
    except (KeyError, TypeError, AttributeError) as error:
        raise FoundryError(f"{ci_gate_path}: not a workflow fragment foundry can read ({error!r})") from None

    return RepoPolicy(rulesets_document["rulesets"], _read_text(policy_dir / "CODEOWNERS"), ci_gate)


def _read_text(file_path: Path) -> str:
    try:
        return file_path.read_text()
    except FileNotFoundError:
        raise FoundryError(f"{file_path} is missing") from None


def deviations(github: GitHub, repo_slug: str, policy: RepoPolicy) -> list[Deviation]:
    """How the repository differs from the policy; empty when it conforms."""
    actual_rulesets = github.rulesets(repo_slug)
    found = [_ruleset_deviation(ruleset, actual_rulesets.get(ruleset["name"])) for ruleset in policy.rulesets]
    found.append(
        compare(
            CODEOWNERS_PATH,
            actual=github.file_text(repo_slug=repo_slug, file_path=CODEOWNERS_PATH),
            expected=policy.codeowners,
        )
    )
    found.append(
        compare(
            CI_WORKFLOW_PATH,
            actual=_project_ci_gate(github.file_text(repo_slug=repo_slug, file_path=CI_WORKFLOW_PATH)),
            expected=policy.ci_gate,
        )
    )
    return [deviation for deviation in found if deviation is not None]


def apply_rulesets(github: GitHub, repo_slug: str, policy: RepoPolicy) -> Iterator[RulesetChange]:
    """Create the policy's rulesets the repository lacks and update those that deviate, in policy order.

    Yields each change once GitHub has made it, so a caller keeps the changes made before a
    failure. Project files are never written: they're the project's to change.
    """
    actual_rulesets = github.rulesets(repo_slug)
    for ruleset in policy.rulesets:
        actual = actual_rulesets.get(ruleset["name"])
        if actual is None:
            github.create_ruleset(repo_slug, ruleset)
            yield RulesetChange(ruleset["name"], RulesetAction.CREATED)
        elif _ruleset_deviation(ruleset, actual) is not None:
            github.update_ruleset(repo_slug, actual["id"], ruleset)
            yield RulesetChange(ruleset["name"], RulesetAction.UPDATED)


@dataclass(frozen=True)
class ProjectCheck:
    """What checking or fixing one repository found: the ruleset changes a fix made, then its deviations, or
    why it couldn't be checked. Changes made before an error are kept."""

    changes: list[RulesetChange]
    deviations: list[Deviation]
    error: str | None = None

    @property
    def conforms(self) -> bool:
        return self.error is None and not self.deviations


def check_project(github: GitHub, repo_url: str, policy: RepoPolicy) -> ProjectCheck:
    """How the repository at ``repo_url`` deviates from the policy; changes nothing.

    A URL that isn't a GitHub repository's, or a GitHub error, is part of the result, not raised.
    """
    try:
        return ProjectCheck([], deviations(github, repo_slug_from_url(repo_url), policy))
    except FoundryError as error:
        return ProjectCheck([], [], error=str(error))


def fix_project(github: GitHub, repo_url: str, policy: RepoPolicy) -> ProjectCheck:
    """Create or update the repository's rulesets to match the policy, then list the deviations left.

    Changes made before an error are kept in the result, with the error, as in check_project.
    """
    changes: list[RulesetChange] = []
    try:
        repo_slug = repo_slug_from_url(repo_url)
        changes.extend(apply_rulesets(github, repo_slug, policy))  # takes each change as it's made
        return ProjectCheck(changes, deviations(github, repo_slug, policy))
    except FoundryError as error:
        return ProjectCheck(changes, [], error=str(error))


def _ruleset_deviation(ruleset: dict[str, Any], actual: dict[str, Any] | None) -> Deviation | None:
    return compare(f"ruleset {ruleset['name']}", actual=restrict_to(expected=ruleset, actual=actual), expected=ruleset)


def _project_ci_gate(workflow_text: str | None) -> dict[str, Any] | None:
    """A project's ci.yml is what's being checked, so a broken one is a deviation, not an error."""
    try:
        workflow = yaml.safe_load(workflow_text) if workflow_text is not None else None
    except yaml.YAMLError:
        return None
    return ci_gate_section(workflow) if isinstance(workflow, dict) else None


def restrict_to(*, expected: Any, actual: Any) -> Any:
    """``actual`` with only the fields ``expected`` has, so fields GitHub adds don't count.

    A list's items are restricted to the fields the expected items have, so
    an extra item, such as another bypass actor, still shows.
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        return {key: restrict_to(expected=expected[key], actual=actual[key]) for key in expected if key in actual}
    if isinstance(expected, list) and isinstance(actual, list):
        return [restrict_to(expected=_expected_item(expected), actual=item) for item in actual]
    return actual


def _expected_item(items: list[Any]) -> Any:
    """What a list's items are expected to look like: every field any expected item has."""
    if not items or not all(isinstance(item, dict) for item in items):
        return items[0] if items else None
    keys = {key for item in items for key in item}
    return {key: _expected_item([item[key] for item in items if key in item]) for key in keys}


def ci_gate_section(workflow: dict[Any, Any]) -> dict[str, Any]:
    """The part of a parsed ci.yml the policy covers: its on: value and its ci-gate job.

    A ci-gate that needs every other job gets the placeholder in place of the
    list, so projects with different jobs compare equal.
    """
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}
    gate = jobs.get(CI_GATE_JOB)
    if (
        isinstance(gate, dict)
        and isinstance(gate.get("needs"), list)
        and set(gate["needs"]) == set(jobs) - {CI_GATE_JOB}
    ):
        gate = {**gate, "needs": ALL_OTHER_JOBS}
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    return {"on": workflow.get("on", workflow.get(True)), "jobs": {CI_GATE_JOB: gate}}


def compare(subject: str, *, actual: Any, expected: Any) -> Deviation | None:
    """The one place that decides whether something matches the policy, and how a deviation reads."""
    if isinstance(expected, str):
        actual_text, expected_text = _normalised(actual), _normalised(expected)
    else:
        actual_text, expected_text = _canonical(actual), _canonical(expected)
    diff = "".join(
        difflib.unified_diff(
            actual_text.splitlines(keepends=True),
            expected_text.splitlines(keepends=True),
            fromfile=f"{subject} (actual)" if actual is not None else f"{subject} (missing)",
            tofile=f"{subject} (repo policy)",
        )
    )
    return Deviation(subject=subject, diff=diff) if diff else None


def _normalised(text: str | None) -> str:
    if text is None:
        return ""
    return "".join(line.rstrip() + "\n" for line in text.rstrip().splitlines())


def _canonical(value: Any) -> str:
    return "" if value is None else json.dumps(_sorted(value), indent=2, sort_keys=True) + "\n"


def _sorted(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted((_sorted(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return value
