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


def test_file_text_is_none_for_a_missing_file_and_errors_otherwise_still_raise() -> None:
    def runner(command: Sequence[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        stderr = "gh: Not Found (HTTP 404)" if command[-1].endswith("missing") else "gh: Bad credentials (HTTP 401)"
        return subprocess.CompletedProcess(command, 1, "", stderr)

    github = GitHub(runner)
    assert github.file_text("o/r", "missing") is None
    with pytest.raises(GitHubError, match="Bad credentials") as error:
        github.file_text("o/r", "CODEOWNERS")
    assert error.value.http_status == 401


def test_rulesets_are_the_repositorys_own_by_name() -> None:
    from tests.fake_github import FakeGitHub

    fake = FakeGitHub()
    fake.add("o/r", {"name": "mine"})
    fake.add("o/r", {"name": "from-the-org"}, source_type="Organization")
    assert list(GitHub(fake).rulesets("o/r")) == ["mine"]
