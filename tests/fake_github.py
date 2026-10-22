"""An in-memory stand-in for `gh api` on the rulesets and contents endpoints."""

import base64
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
        self.files: dict[str, dict[str, str]] = {}
        """File text by repo slug, then path on the default branch."""
        self.unavailable: dict[str, str] = {}
        """Repo slug -> the error gh prints for it, e.g. for a plan without rulesets."""
        self.calls: list[tuple[str, str]] = []
        self._next_id = 1

    def add(self, repo_slug: str, ruleset: dict[str, Any], *, source_type: str = "Repository") -> int:
        ruleset_id = self._next_id
        self._next_id += 1
        stored = {**_as_github_returns(ruleset), **SERVER_FIELDS, "source_type": source_type, "id": ruleset_id}
        self.rulesets.setdefault(repo_slug, {})[ruleset_id] = stored
        return ruleset_id

    def __call__(self, command: Sequence[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        assert list(command[:3]) == ["gh", "api", "--method"], command
        method, endpoint = command[3], command[4]
        self.calls.append((method, endpoint))
        contents = re.fullmatch(r"repos/([^/]+/[^/]+)/contents/(.+)", endpoint)
        if contents:
            text = self.files.get(contents[1], {}).get(contents[2])
            if text is None:
                return subprocess.CompletedProcess([], 1, "", "gh: Not Found (HTTP 404)\n")
            return _ok({"type": "file", "content": base64.b64encode(text.encode()).decode()})

        match = re.fullmatch(r"repos/([^/]+/[^/?]+)/rulesets(?:/(\d+))?(?:\?.*)?", endpoint)
        assert match, endpoint
        slug, ruleset_id = match[1], match[2]
        if slug in self.unavailable:
            return subprocess.CompletedProcess([], 1, "", f"gh: {self.unavailable[slug]}\n")
        repo = self.rulesets.setdefault(slug, {})
        if method == "GET" and ruleset_id is None:
            return _ok([{key: ruleset[key] for key in ("id", "name", "source_type")} for ruleset in repo.values()])
        if method == "GET":
            return _ok(repo[int(ruleset_id)])
        body = json.loads(stdin or "{}")
        if method == "POST":
            return _ok(repo[self.add(slug, body)])
        if method == "PUT":
            repo[int(ruleset_id)] = {**_as_github_returns(body), **SERVER_FIELDS, "id": int(ruleset_id)}
            return _ok(repo[int(ruleset_id)])
        raise AssertionError(f"unexpected call {method} {endpoint}")


def _ok(payload: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, json.dumps(payload), "")


def _as_github_returns(ruleset: dict[str, Any]) -> dict[str, Any]:
    """A copy with each bypass actor's keys in the order GitHub's documented response uses."""
    stored = copy.deepcopy(ruleset)
    stored["bypass_actors"] = [
        {key: actor[key] for key in ("actor_id", "actor_type", "bypass_mode") if key in actor}
        for actor in stored.get("bypass_actors", [])
    ]
    return stored
