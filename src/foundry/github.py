"""GitHub's REST API through the `gh` command line, signed in as the person running foundry.

The foundry never handles a token itself: `gh` holds the login. Agents'
role credentials are never used here.
"""

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

from foundry.errors import FoundryError

Runner = Callable[[Sequence[str], str | None], subprocess.CompletedProcess[str]]
"""Runs a command with optional stdin and returns the finished process."""

_GITHUB_URL = re.compile(
    r"^(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
    r"(?P<owner>[A-Za-z0-9-]+)/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


class GitHubError(FoundryError):
    """A GitHub API call failed; the message is gh's."""


def repo_slug(url: str) -> str:
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


class GitHub:
    def __init__(self, runner: Runner = run_gh) -> None:
        self._runner = runner

    def api(self, method: str, endpoint: str, body: object = None) -> Any:
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
