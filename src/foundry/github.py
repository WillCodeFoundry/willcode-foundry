"""What foundry needs from GitHub, and that implemented through the `gh` command line.

GhCli runs as the person running foundry: `gh` holds the login, so the
foundry never handles a token itself, and agents' role credentials are
never used here.
"""

import base64
import json
import re
import subprocess
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from foundry.errors import FoundryError

Runner = Callable[[Sequence[str], str | None], subprocess.CompletedProcess[str]]
"""Runs a command with optional stdin and returns the finished process."""

_GITHUB_URL = re.compile(
    r"^(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
    r"(?P<owner>[A-Za-z0-9-]+)/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


_HTTP_STATUS = re.compile(r"\(HTTP (\d{3})\)")


class GitHubError(FoundryError):
    """A GitHub API call failed; the message is gh's."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        match = _HTTP_STATUS.search(message)
        self.http_status = int(match[1]) if match else None


def repo_slug_from_url(url: str) -> str:
    """``owner/repo`` for a GitHub clone URL (SSH or HTTPS); raises for anything else."""
    match = _GITHUB_URL.match(url)
    if match is None:
        raise FoundryError(f"{url!r} is not a GitHub repository URL")
    return f"{match['owner']}/{match['repo']}"


def run_gh(command: Sequence[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(list(command), check=False, input=stdin, capture_output=True, text=True)
    except FileNotFoundError:
        raise FoundryError("gh not found in PATH; install the GitHub CLI and run `gh auth login`") from None


class GitHub(Protocol):
    """The interface foundry needs from GitHub: read rulesets and files, create and update rulesets."""

    def rulesets(self, repo_slug: str) -> dict[str, dict[str, Any]]:
        """The repository's own rulesets in full, by name; inherited ones are left out."""
        ...

    def file_text(self, repo_slug: str, file_path: str) -> str | None:
        """A file's text on the default branch, or None if there is no such file."""
        ...

    def create_ruleset(self, repo_slug: str, ruleset: dict[str, Any]) -> None: ...

    def update_ruleset(self, repo_slug: str, ruleset_id: int, ruleset: dict[str, Any]) -> None: ...


class GhCli:
    """GitHub through `gh api`, signed in as the owner. ``runner`` is the seam for this class's own tests."""

    def __init__(self, runner: Runner = run_gh) -> None:
        self._runner = runner

    def _api(self, method: str, endpoint: str, body: object = None) -> Any:
        """Call ``endpoint`` (e.g. ``repos/o/r/rulesets``) and return the decoded JSON response."""
        command = ["gh", "api", "--method", method, endpoint]
        stdin = None
        if body is not None:
            command += ["--input", "-"]
            stdin = json.dumps(body)
        result = self._runner(command, stdin)
        if result.returncode != 0:
            raise GitHubError(result.stderr.strip().removeprefix("gh: ") or f"gh api {endpoint} failed")
        return json.loads(result.stdout) if result.stdout.strip() else None

    def file_text(self, repo_slug: str, file_path: str) -> str | None:
        try:
            content = self._api("GET", f"repos/{repo_slug}/contents/{file_path}")
        except GitHubError as error:
            if error.http_status == 404:
                return None
            raise
        if not isinstance(content, dict) or content.get("type") != "file":
            return None
        return base64.b64decode(content["content"]).decode()

    def rulesets(self, repo_slug: str) -> dict[str, dict[str, Any]]:
        summaries = self._api("GET", f"repos/{repo_slug}/rulesets?per_page=100&includes_parents=false")
        return {
            summary["name"]: self._api("GET", f"repos/{repo_slug}/rulesets/{summary['id']}")
            for summary in summaries
            if summary.get("source_type") == "Repository"
        }

    def create_ruleset(self, repo_slug: str, ruleset: dict[str, Any]) -> None:
        self._api("POST", f"repos/{repo_slug}/rulesets", ruleset)

    def update_ruleset(self, repo_slug: str, ruleset_id: int, ruleset: dict[str, Any]) -> None:
        self._api("PUT", f"repos/{repo_slug}/rulesets/{ruleset_id}", ruleset)
