import subprocess
from collections.abc import Sequence

import pytest

from foundry.errors import FoundryError
from foundry.github import GitHub, GitHubError, repo_slug


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:WillCodeFoundry/tkt-store.git",
        "git@github.com:WillCodeFoundry/tkt-store",
        "ssh://git@github.com/WillCodeFoundry/tkt-store.git",
        "https://github.com/WillCodeFoundry/tkt-store",
        "https://github.com/WillCodeFoundry/tkt-store.git/",
    ],
)
def test_repo_slug_from_github_urls(url: str) -> None:
    assert repo_slug(url) == "WillCodeFoundry/tkt-store"


@pytest.mark.parametrize("url", ["git@gitlab.com:o/r.git", "https://github.com/o", "/srv/git/r.git"])
def test_repo_slug_refuses_other_urls(url: str) -> None:
    with pytest.raises(FoundryError, match="not a GitHub repository URL"):
        repo_slug(url)


def test_api_sends_the_body_on_stdin_and_decodes_the_response() -> None:
    seen: list[tuple[list[str], str | None]] = []

    def runner(command: Sequence[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        seen.append((list(command), stdin))
        return subprocess.CompletedProcess(command, 0, '{"id": 7}', "")

    assert GitHub(runner).api("POST", "repos/o/r/rulesets", {"name": "x"}) == {"id": 7}
    assert seen == [(["gh", "api", "--method", "POST", "repos/o/r/rulesets", "--input", "-"], '{"name": "x"}')]


def test_api_reports_gh_errors_in_gh_words() -> None:
    def runner(command: Sequence[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "gh: Upgrade to GitHub Pro (HTTP 403)\n")

    with pytest.raises(GitHubError, match=r"^Upgrade to GitHub Pro \(HTTP 403\)$"):
        GitHub(runner).api("GET", "repos/o/r/rulesets")
