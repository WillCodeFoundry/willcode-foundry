"""config/github-protection.yaml: the rulesets every project's repository must have."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from foundry import yaml_io
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
class RepoStatus:
    repo_slug: str
    rulesets: list[RulesetStatus]
    unmanaged_ruleset_names: list[str]
    """Rulesets on GitHub that the protection file doesn't name; reported, never changed."""

    @property
    def is_protected(self) -> bool:
        return all(status.state is RulesetState.OK for status in self.rulesets)


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

    Rule lists are matched by rule ``type``; other lists must hold the same
    items, in any order.
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
        if not isinstance(actual, list) or sorted(map(repr, desired)) != sorted(map(repr, actual)):
            return [f"{location}: expected {desired!r}, found {actual!r}"]
        return []
    if desired != actual:
        return [f"{location}: expected {desired!r}, found {actual!r}"]
    return []


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
    return RepoStatus(repo_slug, statuses, unmanaged)


def apply_status(github: GitHub, repo_slug: str, status: RulesetStatus) -> None:
    """Create a missing ruleset or replace one that differs; one that matches is left alone."""
    if status.state is RulesetState.MISSING:
        github.api("POST", f"repos/{repo_slug}/rulesets", status.ruleset)
    elif status.state is RulesetState.DIFFERS:
        github.api("PUT", f"repos/{repo_slug}/rulesets/{status.ruleset_id}", status.ruleset)
