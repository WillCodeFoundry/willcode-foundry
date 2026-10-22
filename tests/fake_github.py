"""An in-memory stand-in for `gh api` on the repository rulesets endpoints."""

import copy
import json
import re
import subprocess
from collections.abc import Sequence
from typing import Any

# Fields GitHub adds to every ruleset it returns; the foundry must ignore them.
SERVER_FIELDS = {"source_type": "Repository", "node_id": "RRS_x", "created_at": "2026-10-22T10:00:00Z"}


class FakeGitHub:
    def __init__(self) -> None:
        self.rulesets: dict[str, dict[int, dict[str, Any]]] = {}
        """Rulesets by repo slug, then id."""
        self.calls: list[tuple[str, str]] = []
        self.unavailable: dict[str, str] = {}
        """Repo slug -> the error gh prints for it, e.g. for a plan without rulesets."""
        self._next_id = 1

    def add(self, repo_slug: str, ruleset: dict[str, Any], *, source_type: str = "Repository") -> int:
        ruleset_id = self._next_id
        self._next_id += 1
        self.rulesets.setdefault(repo_slug, {})[ruleset_id] = {
            **copy.deepcopy(ruleset),
            **SERVER_FIELDS,
            "source_type": source_type,
            "id": ruleset_id,
        }
        return ruleset_id

    def __call__(self, command: Sequence[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        assert list(command[:3]) == ["gh", "api", "--method"], command
        method, endpoint = command[3], command[4]
        self.calls.append((method, endpoint))
        match = re.fullmatch(r"repos/([^/]+/[^/?]+)/rulesets(?:/(\d+))?(?:\?.*)?", endpoint)
        assert match, endpoint
        slug, ruleset_id = match[1], match[2]
        if slug in self.unavailable:
            return subprocess.CompletedProcess(command, 1, "", f"gh: {self.unavailable[slug]}\n")
        repo = self.rulesets.setdefault(slug, {})
        body: dict[str, Any] = json.loads(stdin) if stdin else {}

        if method == "GET" and ruleset_id is None:
            summaries = [
                {key: ruleset[key] for key in ("id", "name", "source_type", "enforcement")} for ruleset in repo.values()
            ]
            return self._ok(summaries)
        if method == "GET":
            return self._ok(repo[int(ruleset_id)])
        if method == "POST":
            return self._ok(repo[self.add(slug, body)])
        if method == "PUT":
            repo[int(ruleset_id)] = {**body, **SERVER_FIELDS, "id": int(ruleset_id)}
            return self._ok(repo[int(ruleset_id)])
        raise AssertionError(f"unexpected call {method} {endpoint}")

    @staticmethod
    def _ok(payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, json.dumps(payload), "")
