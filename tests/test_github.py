"""GhCli, through a runner that records the gh commands it would run and answers them."""

import json
import subprocess
from collections.abc import Sequence

import pytest

from foundry.errors import FoundryError
from foundry.github import GhCli, GitHubError, repo_slug_from_url


class RecordedGh:
    """A runner answering each gh command by its endpoint, recording command and stdin."""

    def __init__(self, answers: dict[str, subprocess.CompletedProcess[str]]) -> None:
        self.answers = answers
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, command: Sequence[str], stdin: str | None) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(command), stdin))
        return self.answers[command[4]]


def ok(payload: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, json.dumps(payload), "")


def failed(stderr: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 1, "", stderr)


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
    assert repo_slug_from_url(url) == "WillCodeFoundry/tkt-store"


@pytest.mark.parametrize("url", ["git@gitlab.com:o/r.git", "https://github.com/o", "/srv/git/r.git"])
def test_repo_slug_refuses_other_urls(url: str) -> None:
    with pytest.raises(FoundryError, match="not a GitHub repository URL"):
        repo_slug_from_url(url)


def test_create_ruleset_sends_the_body_on_stdin_to_the_rulesets_endpoint() -> None:
    gh = RecordedGh({"repos/o/r/rulesets": ok({"id": 7})})

    GhCli(gh).create_ruleset("o/r", {"name": "x"})

    assert gh.calls == [(["gh", "api", "--method", "POST", "repos/o/r/rulesets", "--input", "-"], '{"name": "x"}')]


def test_update_ruleset_puts_the_body_to_that_rulesets_endpoint() -> None:
    gh = RecordedGh({"repos/o/r/rulesets/7": ok({"id": 7})})

    GhCli(gh).update_ruleset("o/r", 7, {"name": "x"})

    assert gh.calls == [(["gh", "api", "--method", "PUT", "repos/o/r/rulesets/7", "--input", "-"], '{"name": "x"}')]


def test_gh_errors_are_reported_in_ghs_words() -> None:
    gh = RecordedGh({"repos/o/r/rulesets": failed("gh: Upgrade to GitHub Pro (HTTP 403)\n")})

    with pytest.raises(GitHubError, match=r"^Upgrade to GitHub Pro \(HTTP 403\)$"):
        GhCli(gh).create_ruleset("o/r", {"name": "x"})


def test_a_missing_file_is_none_and_other_errors_still_raise() -> None:
    gh = RecordedGh(
        {
            "repos/o/r/contents/missing": failed("gh: Not Found (HTTP 404)"),
            "repos/o/r/contents/CODEOWNERS": failed("gh: Bad credentials (HTTP 401)"),
        }
    )

    assert GhCli(gh).file_text(repo_slug="o/r", file_path="missing") is None
    with pytest.raises(GitHubError, match="Bad credentials") as error:
        GhCli(gh).file_text(repo_slug="o/r", file_path="CODEOWNERS")
    assert error.value.http_status == 401


def test_rulesets_are_the_repositorys_own_by_name() -> None:
    gh = RecordedGh(
        {
            "repos/o/r/rulesets?per_page=100&includes_parents=false": ok(
                [
                    {"id": 1, "name": "mine", "source_type": "Repository"},
                    {"id": 2, "name": "from-the-org", "source_type": "Organization"},
                ]
            ),
            "repos/o/r/rulesets/1": ok({"id": 1, "name": "mine", "enforcement": "active"}),
        }
    )

    assert GhCli(gh).rulesets("o/r") == {"mine": {"id": 1, "name": "mine", "enforcement": "active"}}
