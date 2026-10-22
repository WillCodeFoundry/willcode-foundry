"""An in-memory stand-in for `gh api` on the repository rulesets and contents endpoints."""

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
        self.calls: list[tuple[str, str]] = []
        self.files: dict[str, dict[str, str]] = {}
        """File text by repo slug, then path on the default branch."""
        self.permissions: dict[str, dict[str, str]] = {}
        """Base access by repo slug, then username; anyone else is not a collaborator."""
        self.default_branches: dict[str, str] = {}
        """Default branch by repo slug; main unless set."""
        self.unavailable: dict[str, str] = {}
        """Repo slug -> the error gh prints for it, e.g. for a plan without rulesets."""
        self._next_id = 1

    def add(self, repo_slug: str, ruleset: dict[str, Any], *, source_type: str = "Repository") -> int:
        ruleset_id = self._next_id
        self._next_id += 1
        self.rulesets.setdefault(repo_slug, {})[ruleset_id] = {
            **_as_github_returns(ruleset),
            **SERVER_FIELDS,
            "source_type": source_type,
            "id": ruleset_id,
        }
        return ruleset_id

    def __call__(self, command: Sequence[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        assert list(command[:3]) == ["gh", "api", "--method"], command
        method, endpoint = command[3], command[4]
        self.calls.append((method, endpoint))
        if re.fullmatch(r"repos/[^/]+/[^/]+", endpoint):
            return self._ok({"default_branch": self.default_branches.get(endpoint.removeprefix("repos/"), "main")})
        permission = re.fullmatch(r"repos/([^/]+/[^/]+)/collaborators/([^/]+)/permission", endpoint)
        if permission:
            access = self.permissions.get(permission[1], {}).get(permission[2])
            if access is None:
                return subprocess.CompletedProcess([], 1, "", "gh: Not Found (HTTP 404)\n")
            return self._ok({"permission": access, "role_name": access})
        contents = re.fullmatch(r"repos/([^/]+/[^/]+)/contents/(.+)", endpoint)
        if contents:
            return self._contents(contents[1], contents[2])
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
            repo[int(ruleset_id)] = {**_as_github_returns(body), **SERVER_FIELDS, "id": int(ruleset_id)}
            return self._ok(repo[int(ruleset_id)])
        raise AssertionError(f"unexpected call {method} {endpoint}")

    def _contents(self, slug: str, path: str) -> subprocess.CompletedProcess[str]:
        files = self.files.get(slug, {})
        if path in files:
            return self._ok({"type": "file", "path": path, "content": base64.b64encode(files[path].encode()).decode()})
        entries = sorted({f.removeprefix(f"{path}/").split("/")[0] for f in files if f.startswith(f"{path}/")})
        if not entries:
            return subprocess.CompletedProcess([], 1, "", "gh: Not Found (HTTP 404)\n")
        listing = [
            {"path": f"{path}/{name}", "type": "file" if f"{path}/{name}" in files else "dir"} for name in entries
        ]
        return self._ok(listing)

    @staticmethod
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
