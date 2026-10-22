"""Reading a project's own files: which jobs its workflows run on pull requests, and its CODEOWNERS."""

import re
from typing import Any

import yaml

CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
"""Where GitHub looks for CODEOWNERS, in the order it looks."""

WORKFLOWS_DIR_PATH = ".github/workflows"


def pull_request_check_names(workflow_text: str) -> set[str]:
    """Check names a workflow reports on pull requests: each job's ``name``, or its id.

    Empty if the workflow doesn't run on ``pull_request`` or can't be read.
    Matrix jobs get suffixed names on GitHub, so their bare names are not checks.
    """
    try:
        workflow = yaml.safe_load(workflow_text)
    except yaml.YAMLError:
        return set()
    if not isinstance(workflow, dict) or "pull_request" not in _triggers(workflow):
        return set()
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return set()
    return {
        str(job.get("name", job_id))
        for job_id, job in jobs.items()
        if isinstance(job, dict) and "matrix" not in (job.get("strategy") or {})
    }


def _triggers(workflow: dict[object, object]) -> set[str]:
    on = _on(workflow)
    if isinstance(on, str):
        return {on}
    if isinstance(on, list | dict):
        return {str(trigger) for trigger in on}
    return set()


def _on(workflow: dict[object, object]) -> object:
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    return workflow.get("on", workflow.get(True))


def gating_problems(workflow_text: str, check_name: str, default_branch: str) -> list[str]:
    """Why a job this workflow reports as ``check_name`` might not gate pull requests into ``default_branch``.

    Two ways to go wrong. A filter that stops the workflow running leaves the
    check pending, so pull requests can't merge. A condition that skips the
    job is worse: GitHub counts a skipped check as passed, so pull requests
    merge without CI. A job that needs others is skipped when one of them
    fails, unless its condition is always().
    """
    workflow = yaml.safe_load(workflow_text)
    problems = []
    on = _on(workflow)
    pull_request = on.get("pull_request") if isinstance(on, dict) else None
    if isinstance(pull_request, dict):
        for key in ("paths", "paths-ignore", "branches-ignore"):
            if key in pull_request:
                problems.append(f"pull_request has a {key} filter, so some pull requests never get {check_name}")
        branches = pull_request.get("branches")
        if branches is not None and not _branch_filter_matches(_as_list(branches), default_branch):
            problems.append(f"pull_request's branches filter leaves out {default_branch}")
    job = _job_named(workflow, check_name)
    condition = _expression(job.get("if")) if job is not None and "if" in job else None
    if condition is not None and condition != "always()":
        problems.append(f"{check_name} has if: {condition}; when it skips the job, GitHub counts it as passed")
    elif condition is None and job is not None and job.get("needs"):
        problems.append(
            f"{check_name} needs other jobs but has no if: always(); when one fails it is skipped, "
            "and GitHub counts a skipped check as passed"
        )
    return problems


def _job_named(workflow: dict[str, Any], check_name: str) -> dict[str, Any] | None:
    for job_id, job in (workflow.get("jobs") or {}).items():
        if isinstance(job, dict) and str(job.get("name", job_id)) == check_name:
            return job
    return None


def _expression(condition: object) -> str:
    text = str(condition).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    return text


def _as_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def _branch_filter_matches(patterns: list[str], branch: str) -> bool:
    """GitHub's branch filter: patterns in order, a later !pattern excluding what earlier ones matched."""
    matched = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        if _glob_regex(pattern.removeprefix("!")).fullmatch(branch):
            matched = not negated
    return matched


def _glob_regex(pattern: str) -> re.Pattern[str]:
    regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", ".")
    return re.compile(regex)


CATCH_ALL_PATTERNS = ("*", "**", "/**")
"""CODEOWNERS patterns that match every file in the repository."""


def codeowners_lines(codeowners_text: str) -> list[tuple[str, list[str]]]:
    """Each CODEOWNERS line as (pattern, owners), comments and blank lines left out.

    An owner is ``@user``, ``@org/team`` or an email address. A line may name
    no owners, which leaves the files it matches without one.
    """
    lines = []
    for line in codeowners_text.splitlines():
        fields = line.split("#", 1)[0].split()
        if fields:
            lines.append((fields[0], fields[1:]))
    return lines
