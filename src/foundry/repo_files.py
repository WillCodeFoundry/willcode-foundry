"""Reading a project's own files: which jobs its workflows run on pull requests, and who owns a path."""

import re

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
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list | dict):
        return {str(trigger) for trigger in on}
    return set()


def owners(codeowners_text: str, file_path: str) -> list[str]:
    """The owners CODEOWNERS gives ``file_path``: the last matching line wins, and may name none."""
    found: list[str] = []
    for line in codeowners_text.splitlines():
        fields = line.split("#", 1)[0].split()
        if fields and _pattern_regex(fields[0]).fullmatch(file_path):
            found = fields[1:]
    return found


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    """A CODEOWNERS (gitignore-style) pattern as a regex over repository-relative paths."""
    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    body = pattern.strip("/")
    if pattern.endswith("/"):
        body += "/**"
    regex = ""
    i = 0
    while i < len(body):
        if body.startswith("**", i):
            regex += ".*"
            i += 2
        elif body[i] == "*":
            regex += "[^/]*"
            i += 1
        elif body[i] == "?":
            regex += "[^/]"
            i += 1
        else:
            regex += re.escape(body[i])
            i += 1
    prefix = "" if anchored else "(?:.*/)?"
    return re.compile(f"{prefix}{regex}(?:/.*)?")
