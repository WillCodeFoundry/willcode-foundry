"""config/github-protection.yaml: the rulesets every project's repository must have.

Some rules only work if the project's own files cooperate: a required status
check must be produced by a workflow job on pull requests, and a required
code owner review needs a CODEOWNERS file in which admins own every file.
Those are checked and reported, never changed: they belong to the project.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from foundry import repo_files, yaml_io
from foundry.errors import FoundryError
from foundry.github import GitHub

Ruleset = dict[str, Any]
"""A ruleset in the shape of GitHub's REST API."""


class RulesetState(StrEnum):
    OK = "ok"
    MISSING = "missing"
    DIFFERS = "differs"


@dataclass(frozen=True)
class RulesetStatus:
    ruleset: Ruleset
    """The desired ruleset, from the protection file."""
    state: RulesetState
    differences: list[str] = field(default_factory=list)
    ruleset_id: int | None = None
    """GitHub's id for the ruleset of the same name, if there is one."""

    @property
    def ruleset_name(self) -> str:
        return str(self.ruleset["name"])


@dataclass(frozen=True)
class FileCheck:
    """Whether the project's own files support a rule; fixed in the project, not by apply."""

    description: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class RepoStatus:
    repo_slug: str
    rulesets: list[RulesetStatus]
    unmanaged_ruleset_names: list[str]
    """Rulesets on GitHub that the protection file doesn't name; reported, never changed."""
    file_checks: list[FileCheck] = field(default_factory=list)

    @property
    def rulesets_match(self) -> bool:
        return all(status.state is RulesetState.OK for status in self.rulesets)

    @property
    def files_ok(self) -> bool:
        return all(check.ok for check in self.file_checks)

    @property
    def is_protected(self) -> bool:
        return self.rulesets_match and self.files_ok


def load(protection_path: Path) -> list[Ruleset]:
    return parse(yaml_io.load(protection_path), source=str(protection_path))


def parse(raw: object, *, source: str = "protection file") -> list[Ruleset]:
    if not isinstance(raw, dict) or not isinstance(raw.get("rulesets"), list):
        raise FoundryError(f"{source}: needs a 'rulesets' list")
    rulesets: list[Ruleset] = []
    seen_names: set[str] = set()
    for index, ruleset in enumerate(raw["rulesets"]):
        name = ruleset.get("name") if isinstance(ruleset, dict) else None
        if not isinstance(name, str) or not name:
            raise FoundryError(f"{source}: rulesets[{index}] needs a 'name'")
        if name in seen_names:
            raise FoundryError(f"{source}: ruleset {name!r} is listed twice")
        seen_names.add(name)
        rulesets.append(ruleset)
    return rulesets


def differences(desired: object, actual: object, location: str = "") -> list[str]:
    """Where ``actual`` falls short of ``desired``; fields only ``actual`` has are ignored.

    Rule lists are matched by rule ``type``. Other lists must hold as many
    items as ``desired``, each matching one of its items in any order, with
    mappings compared as above: key order and extra fields don't matter, but
    an extra item, such as another bypass actor, does.
    """
    if isinstance(desired, dict):
        if not isinstance(actual, dict):
            return [f"{location or 'value'}: expected a mapping, found {actual!r}"]
        found: list[str] = []
        for key, value in desired.items():
            key_location = f"{location}.{key}" if location else str(key)
            if key not in actual:
                found.append(f"{key_location}: missing")
            else:
                found += differences(value, actual[key], key_location)
        return found
    if isinstance(desired, list) and _is_rule_list(desired):
        actual_rules = (
            {rule.get("type"): rule for rule in actual if isinstance(rule, dict)} if isinstance(actual, list) else {}
        )
        found = []
        for rule in desired:
            rule_location = f"{location}[{rule['type']}]"
            if rule["type"] not in actual_rules:
                found.append(f"{rule_location}: missing")
            else:
                found += differences(rule, actual_rules[rule["type"]], rule_location)
        return found
    if isinstance(desired, list):
        if not isinstance(actual, list) or not _same_items(desired, actual):
            return [f"{location}: expected {desired!r}, found {actual!r}"]
        return []
    if desired != actual:
        return [f"{location}: expected {desired!r}, found {actual!r}"]
    return []


def _same_items(desired: list[Any], actual: list[Any]) -> bool:
    if len(desired) != len(actual):
        return False
    unmatched = list(actual)
    for item in desired:
        match = next((candidate for candidate in unmatched if not differences(item, candidate)), _NO_MATCH)
        if match is _NO_MATCH:
            return False
        unmatched.remove(match)
    return True


_NO_MATCH = object()


def _is_rule_list(items: list[Any]) -> bool:
    return bool(items) and all(isinstance(item, dict) and isinstance(item.get("type"), str) for item in items)


def check_repo(github: GitHub, repo_slug: str, rulesets: list[Ruleset]) -> RepoStatus:
    """Compare the repository's own rulesets (not inherited ones) with ``rulesets``."""
    summaries = github.api("GET", f"repos/{repo_slug}/rulesets?per_page=100&includes_parents=false")
    ids_by_name = {
        summary["name"]: summary["id"] for summary in summaries if summary.get("source_type") == "Repository"
    }
    statuses = []
    for ruleset in rulesets:
        ruleset_id = ids_by_name.get(ruleset["name"])
        if ruleset_id is None:
            statuses.append(RulesetStatus(ruleset, RulesetState.MISSING))
            continue
        actual = github.api("GET", f"repos/{repo_slug}/rulesets/{ruleset_id}")
        found = differences(ruleset, actual)
        state = RulesetState.DIFFERS if found else RulesetState.OK
        statuses.append(RulesetStatus(ruleset, state, found, ruleset_id))
    managed = {ruleset["name"] for ruleset in rulesets}
    unmanaged = sorted(name for name in ids_by_name if name not in managed)
    return RepoStatus(repo_slug, statuses, unmanaged, check_project_files(github, repo_slug, rulesets))


def required_check_names(rulesets: list[Ruleset]) -> list[str]:
    """The status check names the rulesets require, in order, without repeats."""
    names: list[str] = []
    for rule in _rules(rulesets, "required_status_checks"):
        for check in rule.get("parameters", {}).get("required_status_checks", []):
            if check["context"] not in names:
                names.append(check["context"])
    return names


def requires_code_owner_review(rulesets: list[Ruleset]) -> bool:
    return any(rule.get("parameters", {}).get("require_code_owner_review") for rule in _rules(rulesets, "pull_request"))


def _rules(rulesets: list[Ruleset], rule_type: str) -> list[dict[str, Any]]:
    return [rule for ruleset in rulesets for rule in ruleset.get("rules", []) if rule.get("type") == rule_type]


def check_project_files(github: GitHub, repo_slug: str, rulesets: list[Ruleset]) -> list[FileCheck]:
    """Check the default branch's workflows and CODEOWNERS against what the rulesets require."""
    check_names = required_check_names(rulesets)
    needs_code_owners = requires_code_owner_review(rulesets)
    if not check_names and not needs_code_owners:
        return []
    workflow_paths = [
        path
        for path in github.dir_file_paths(repo_slug, repo_files.WORKFLOWS_DIR_PATH)
        if path.endswith((".yml", ".yaml"))
    ]
    checks = [_check_workflows_produce(github, repo_slug, workflow_paths, name) for name in check_names]
    if needs_code_owners:
        checks.append(_check_code_owners(github, repo_slug))
    return checks


def _check_workflows_produce(github: GitHub, repo_slug: str, workflow_paths: list[str], check_name: str) -> FileCheck:
    producers = [
        path
        for path in workflow_paths
        if check_name in repo_files.pull_request_check_names(github.file_text(repo_slug, path) or "")
    ]
    description = f"required check {check_name}"
    if producers:
        return FileCheck(description, True, ", ".join(producers))
    return FileCheck(description, False, "no workflow on the default branch runs a job of that name on pull requests")


def _check_code_owners(github: GitHub, repo_slug: str) -> FileCheck:
    """Code owner review only keeps agents from merging if an admin owns every file.

    Agents' users have write access, and so does the reviewer role: one
    approval from it would do for any file without an owner, or owned by
    someone who isn't an admin. So CODEOWNERS needs a catch-all line, no line
    that leaves files unowned, and admins as its only owners.
    """
    for codeowners_path in repo_files.CODEOWNERS_PATHS:
        text = github.file_text(repo_slug, codeowners_path)
        if text is not None:
            break
    else:
        return FileCheck("CODEOWNERS", False, "no CODEOWNERS file, but code owner review is required")

    lines = repo_files.codeowners_lines(text)
    problems = []
    if not any(pattern in repo_files.CATCH_ALL_PATTERNS and owners for pattern, owners in lines):
        problems.append("no catch-all line such as '* @you': files it doesn't list need no admin's approval")
    unowning = [pattern for pattern, owners in lines if not owners]
    if unowning:
        problems.append(f"lines that leave files without an owner: {', '.join(unowning)}")
    for owner in sorted({owner for _, owners in lines for owner in owners}):
        if not owner.startswith("@") or "/" in owner:
            problems.append(f"{owner} can't be checked; name admins by @username")
        elif (access := github.permission(repo_slug, owner.removeprefix("@"))) != "admin":
            problems.append(f"{owner} has {access} access, not admin")
    if problems:
        return FileCheck("CODEOWNERS", False, "; ".join(problems))
    return FileCheck("CODEOWNERS", True, f"{codeowners_path}: admins own every file")


def apply_status(github: GitHub, repo_slug: str, status: RulesetStatus) -> None:
    """Create a missing ruleset or replace one that differs; one that matches is left alone."""
    if status.state is RulesetState.MISSING:
        github.api("POST", f"repos/{repo_slug}/rulesets", status.ruleset)
    elif status.state is RulesetState.DIFFERS:
        github.api("PUT", f"repos/{repo_slug}/rulesets/{status.ruleset_id}", status.ruleset)
