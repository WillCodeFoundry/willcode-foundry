"""Fakes for the foundry package's interfaces. agent_sandbox's are in tests/agent_sandbox/fakes.py."""

import copy
from typing import Any

from foundry.github import GitHub, GitHubError


class FakeGitHub:
    """GitHub in memory, as foundry.github.GitHub describes it."""

    def __init__(self) -> None:
        self.stored_rulesets: dict[str, dict[str, dict[str, Any]]] = {}
        """Rulesets by repo slug, then by name; each stored with the id GitHub would give it."""
        self.files: dict[str, dict[str, str]] = {}
        """File text by repo slug, then path on the default branch."""
        self.unavailable: dict[str, str] = {}
        """Repo slug -> the message GitHub refuses it with, e.g. for a plan without rulesets."""
        self._next_id = 1

    def rulesets(self, repo_slug: str) -> dict[str, dict[str, Any]]:
        if repo_slug in self.unavailable:
            raise GitHubError(self.unavailable[repo_slug])
        return copy.deepcopy(self.stored_rulesets.get(repo_slug, {}))

    def file_text(self, *, repo_slug: str, file_path: str) -> str | None:
        return self.files.get(repo_slug, {}).get(file_path)

    def create_ruleset(self, repo_slug: str, ruleset: dict[str, Any]) -> None:
        self.stored_rulesets.setdefault(repo_slug, {})[ruleset["name"]] = {
            **copy.deepcopy(ruleset),
            "id": self._next_id,
        }
        self._next_id += 1

    def update_ruleset(self, repo_slug: str, ruleset_id: int, ruleset: dict[str, Any]) -> None:
        repo = self.stored_rulesets[repo_slug]
        (name,) = [name for name, stored in repo.items() if stored["id"] == ruleset_id]
        del repo[name]
        repo[ruleset["name"]] = {**copy.deepcopy(ruleset), "id": ruleset_id}

    def ruleset_id(self, repo_slug: str, ruleset_name: str) -> int:
        return int(self.stored_rulesets[repo_slug][ruleset_name]["id"])


_: type[GitHub] = FakeGitHub  # FakeGitHub implements the protocol
