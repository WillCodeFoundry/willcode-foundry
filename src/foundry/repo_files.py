"""Reading a project's own files: which jobs its workflows run on pull requests, and its CODEOWNERS."""

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
