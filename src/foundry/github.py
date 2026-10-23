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
    """The interface foundry needs from GitHub: rulesets, branches and files."""

    def rulesets(self, repo_slug: str) -> dict[str, dict[str, Any]]:
        """The repository's own rulesets in full, by name; inherited ones are left out."""
        ...

    def file_text(self, repo_slug: str, file_path: str, branch: str | None = None) -> str | None:
        """A file's text on ``branch`` (default: the default branch), or None if there is no such file."""
        ...

    def default_branch(self, repo_slug: str) -> str: ...

    def branch_head(self, repo_slug: str, branch: str) -> str | None:
        """The commit sha ``branch`` points at, or None if there is no such branch."""
        ...

    def create_branch(self, repo_slug: str, branch: str, sha: str) -> None: ...

    def create_orphan_branch(self, repo_slug: str, branch: str, file_path: str, text: str, commit_message: str) -> None:
        """Create ``branch`` whose one commit holds only this file, sharing no history with other branches."""
        ...

    def create_file(self, repo_slug: str, branch: str, file_path: str, text: str, commit_message: str) -> None:
        """Commit a new file to ``branch``; GitHub refuses one that already exists."""
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

    def _get_or_none(self, endpoint: str) -> Any:
        """GET ``endpoint``; None if GitHub answers 404."""
        try:
            return self._api("GET", endpoint)
        except GitHubError as error:
            if error.http_status == 404:
                return None
            raise

    def file_text(self, repo_slug: str, file_path: str, branch: str | None = None) -> str | None:
        ref = f"?ref={branch}" if branch else ""
        content = self._get_or_none(f"repos/{repo_slug}/contents/{file_path}{ref}")
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

    def default_branch(self, repo_slug: str) -> str:
        return str(self._api("GET", f"repos/{repo_slug}")["default_branch"])

    def branch_head(self, repo_slug: str, branch: str) -> str | None:
        ref = self._get_or_none(f"repos/{repo_slug}/git/ref/heads/{branch}")
        return None if ref is None else str(ref["object"]["sha"])

    def create_branch(self, repo_slug: str, branch: str, sha: str) -> None:
        self._api("POST", f"repos/{repo_slug}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})

    def create_orphan_branch(self, repo_slug: str, branch: str, file_path: str, text: str, commit_message: str) -> None:
        blob = {"path": file_path, "mode": "100644", "type": "blob", "content": text}
        tree = self._api("POST", f"repos/{repo_slug}/git/trees", {"tree": [blob]})
        commit_body = {"message": commit_message, "tree": tree["sha"], "parents": []}
        commit = self._api("POST", f"repos/{repo_slug}/git/commits", commit_body)
        self.create_branch(repo_slug, branch, commit["sha"])

    def create_file(self, repo_slug: str, branch: str, file_path: str, text: str, commit_message: str) -> None:
        content = base64.b64encode(text.encode()).decode()
        body = {"message": commit_message, "content": content, "branch": branch}
        self._api("PUT", f"repos/{repo_slug}/contents/{file_path}", body)
