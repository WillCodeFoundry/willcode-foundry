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

    assert GhCli(gh).file_text("o/r", "missing") is None
    with pytest.raises(GitHubError, match="Bad credentials") as error:
        GhCli(gh).file_text("o/r", "CODEOWNERS")
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


# --- branches and files ---------------------------------------------------------


def test_file_text_reads_another_branch_by_ref() -> None:
    gh = RecordedGh({"repos/o/r/contents/a.md?ref=agent-notes": ok({"type": "file", "content": "aGk="})})

    assert GhCli(gh).file_text("o/r", "a.md", "agent-notes") == "hi"


def test_branch_head_is_the_sha_or_none_for_a_missing_branch() -> None:
    gh = RecordedGh(
        {
            "repos/o/r/git/ref/heads/main": ok({"object": {"sha": "abc"}}),
            "repos/o/r/git/ref/heads/gone": failed("gh: Not Found (HTTP 404)"),
        }
    )

    assert GhCli(gh).branch_head("o/r", "main") == "abc"
    assert GhCli(gh).branch_head("o/r", "gone") is None


def test_default_branch_comes_from_the_repository() -> None:
    assert GhCli(RecordedGh({"repos/o/r": ok({"default_branch": "trunk"})})).default_branch("o/r") == "trunk"


def test_commit_files_adds_one_commit_on_top_of_the_branch() -> None:
    gh = RecordedGh(
        {
            "repos/o/r/git/ref/heads/agent-notes": ok({"object": {"sha": "head-sha"}}),
            "repos/o/r/git/commits/head-sha": ok({"tree": {"sha": "head-tree"}}),
            "repos/o/r/git/trees": ok({"sha": "tree-sha"}),
            "repos/o/r/git/commits": ok({"sha": "commit-sha"}),
            "repos/o/r/git/refs/heads/agent-notes": ok({}),
        }
    )

    GhCli(gh).commit_files("o/r", "agent-notes", {".agent/T1/TASK.md": "# T1\n"}, "Add task T1")

    bodies = {command[4]: json.loads(stdin) for command, stdin in gh.calls if stdin}
    assert bodies["repos/o/r/git/trees"]["base_tree"] == "head-tree"
    assert bodies["repos/o/r/git/commits"]["parents"] == ["head-sha"]
    assert bodies["repos/o/r/git/refs/heads/agent-notes"] == {"sha": "commit-sha"}


def test_create_orphan_branch_makes_a_parentless_commit_of_the_files_and_points_the_branch_at_it() -> None:
    gh = RecordedGh(
        {
            "repos/o/r/git/trees": ok({"sha": "tree-sha"}),
            "repos/o/r/git/commits": ok({"sha": "commit-sha"}),
            "repos/o/r/git/refs": ok({}),
        }
    )

    GhCli(gh).create_orphan_branch("o/r", "agent-notes", {".agent/T1/TASK.md": "# T1\n"}, "Add task T1")

    bodies = [json.loads(stdin or "") for _, stdin in gh.calls]
    assert bodies[0] == {"tree": [{"path": ".agent/T1/TASK.md", "mode": "100644", "type": "blob", "content": "# T1\n"}]}
    assert bodies[1] == {"message": "Add task T1", "tree": "tree-sha", "parents": []}
    assert bodies[2] == {"ref": "refs/heads/agent-notes", "sha": "commit-sha"}
