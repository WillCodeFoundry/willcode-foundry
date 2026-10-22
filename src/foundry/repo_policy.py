"""The repo policy: what every project's GitHub repository must match.

config/repo-policy/ holds the rulesets, the CODEOWNERS file and the ci-gate
section of ci.yml (when it runs, and its ci-gate job) that the rulesets
depend on. A repository is checked by comparing it with these, not by
analysing what it has: anything different is a deviation, even when
harmless. When a project really needs to differ, change the policy.
"""

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from foundry import yaml_io
from foundry.errors import FoundryError
from foundry.github import GitHub

CODEOWNERS_PATH = ".github/CODEOWNERS"
CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
CI_GATE_JOB = "ci-gate"
ALL_OTHER_JOBS = "<all other jobs>"


@dataclass(frozen=True)
class RepoPolicy:
    rulesets: list[dict[str, Any]]
    codeowners: str
    ci_gate: dict[str, Any]


@dataclass(frozen=True)
class Deviation:
    """One way a repository differs from the repo policy, as a diff from it to the policy."""

    subject: str
    diff: str


def load(policy_dir: Path) -> RepoPolicy:
    """Read config/repo-policy/; a file that's missing or not what foundry expects fails with its path."""
    rulesets_path = policy_dir / "rulesets.yaml"
    ci_gate_path = policy_dir / "ci-gate.yml"
    try:
        rulesets = yaml_io.load(rulesets_path)["rulesets"]
        ci_gate = ci_gate_section(yaml_io.load(ci_gate_path))
    except (KeyError, TypeError, AttributeError) as error:
        raise FoundryError(f"{policy_dir}: not a repo policy foundry can read ({error!r})") from None
    return RepoPolicy(rulesets, _read_text(policy_dir / "CODEOWNERS"), ci_gate)


def _read_text(file_path: Path) -> str:
    try:
        return file_path.read_text()
    except FileNotFoundError:
        raise FoundryError(f"{file_path} is missing") from None


def deviations(github: GitHub, repo_slug: str, policy: RepoPolicy) -> list[Deviation]:
    """How the repository differs from the policy; empty when it conforms."""
    actual_rulesets = github.rulesets(repo_slug)
    found = [
        compare(f"ruleset {ruleset['name']}", restrict_to(ruleset, actual_rulesets.get(ruleset["name"])), ruleset)
        for ruleset in policy.rulesets
    ]
    found.append(compare(CODEOWNERS_PATH, github.file_text(repo_slug, CODEOWNERS_PATH), policy.codeowners))
    found.append(
        compare(CI_WORKFLOW_PATH, _project_ci_gate(github.file_text(repo_slug, CI_WORKFLOW_PATH)), policy.ci_gate)
    )
    return [deviation for deviation in found if deviation is not None]


def _project_ci_gate(workflow_text: str | None) -> dict[str, Any] | None:
    """A project's ci.yml is what's being checked, so a broken one is a deviation, not an error."""
    try:
        workflow = yaml.safe_load(workflow_text) if workflow_text is not None else None
    except yaml.YAMLError:
        return None
    return ci_gate_section(workflow) if isinstance(workflow, dict) else None


def restrict_to(expected: Any, actual: Any) -> Any:
    """``actual`` with only the fields ``expected`` has, so fields GitHub adds don't count.

    A list's items are restricted to the fields the expected items have, so
    an extra item, such as another bypass actor, still shows.
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        return {key: restrict_to(expected[key], actual[key]) for key in expected if key in actual}
    if isinstance(expected, list) and isinstance(actual, list):
        return [restrict_to(_expected_item(expected), item) for item in actual]
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


def compare(subject: str, actual: Any, expected: Any) -> Deviation | None:
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
    return Deviation(subject, diff) if diff else None


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
