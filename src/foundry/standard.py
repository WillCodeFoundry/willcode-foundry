"""The project standard: what every project's GitHub repository must match.

config/project-standard/ holds the rulesets, the CODEOWNERS file and the part
of ci.yml (when it runs, and its ci-gate job) that the rulesets depend on. A
project is checked by comparing it with these, not by analysing what it has:
anything different is a finding, even when harmless. When a project really
needs to differ, change the standard.
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
CI_PATH = ".github/workflows/ci.yml"
GATE_JOB = "ci-gate"
ALL_OTHER_JOBS = "<all other jobs>"


@dataclass(frozen=True)
class Standard:
    rulesets: list[dict[str, Any]]
    codeowners: str
    ci_fragment: dict[str, Any]


@dataclass(frozen=True)
class Finding:
    """One subject compared with the standard; an empty diff means it matches."""

    subject: str
    diff: str


def load(standard_path: Path) -> Standard:
    raw = yaml_io.load(standard_path / "rulesets.yaml")
    if not isinstance(raw, dict) or not isinstance(raw.get("rulesets"), list):
        raise FoundryError(f"{standard_path / 'rulesets.yaml'}: needs a 'rulesets' list")
    ci_fragment = fragment((standard_path / "ci-gate.yml").read_text())
    if ci_fragment is None:
        raise FoundryError(f"{standard_path / 'ci-gate.yml'}: needs an on: block and a {GATE_JOB} job")
    return Standard(raw["rulesets"], (standard_path / "CODEOWNERS").read_text(), ci_fragment)


def check(github: GitHub, repo_slug: str, standard: Standard) -> list[Finding]:
    actual_rulesets = github.rulesets(repo_slug)
    findings = [
        compare(f"ruleset {ruleset['name']}", project(actual_rulesets.get(ruleset["name"]), ruleset), ruleset)
        for ruleset in standard.rulesets
    ]
    findings.append(compare(CODEOWNERS_PATH, github.file_text(repo_slug, CODEOWNERS_PATH), standard.codeowners))
    ci_text = github.file_text(repo_slug, CI_PATH)
    findings.append(compare(CI_PATH, fragment(ci_text) if ci_text is not None else None, standard.ci_fragment))
    return findings


def project(actual: Any, template: Any) -> Any:
    """``actual`` with only the fields ``template`` has, so fields GitHub adds don't count.

    A list's items are projected onto the union of the template items' fields,
    so an extra item, such as another bypass actor, still shows.
    """
    if isinstance(template, dict) and isinstance(actual, dict):
        return {key: project(actual[key], template[key]) for key in template if key in actual}
    if isinstance(template, list) and isinstance(actual, list):
        return [project(item, _union(template)) for item in actual]
    return actual


def _union(items: list[Any]) -> Any:
    if not items or not all(isinstance(item, dict) for item in items):
        return items[0] if items else None
    keys = {key for item in items for key in item}
    return {key: _union([item[key] for item in items if key in item]) for key in keys}


def fragment(ci_text: str) -> dict[str, Any] | None:
    """The part of a ci.yml the standard covers: its on: value and its ci-gate job.

    A ci-gate that needs every other job gets the placeholder in place of the
    list, so projects with different jobs compare equal.
    """
    try:
        workflow = yaml.safe_load(ci_text)
    except yaml.YAMLError:
        return None
    if not isinstance(workflow, dict):
        return None
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}
    gate = jobs.get(GATE_JOB)
    if isinstance(gate, dict) and isinstance(gate.get("needs"), list) and set(gate["needs"]) == set(jobs) - {GATE_JOB}:
        gate = {**gate, "needs": ALL_OTHER_JOBS}
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    return {"on": workflow.get("on", workflow.get(True)), "jobs": {GATE_JOB: gate}}


def compare(subject: str, actual: Any, standard: Any) -> Finding:
    """The one place that decides whether something matches the standard, and how a mismatch reads."""
    if isinstance(standard, str):
        actual_text, standard_text = _normalised(actual), _normalised(standard)
    else:
        actual_text, standard_text = _canonical(actual), _canonical(standard)
    lines = difflib.unified_diff(
        actual_text.splitlines(keepends=True),
        standard_text.splitlines(keepends=True),
        fromfile=f"{subject} (actual)" if actual is not None else f"{subject} (missing)",
        tofile=f"{subject} (standard)",
    )
    return Finding(subject, "".join(lines))


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
