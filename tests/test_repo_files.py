import pytest

from foundry.repo_files import owners, pull_request_check_names

CI = """\
name: ci
on:
  pull_request:
  push:
    branches: [main]
jobs:
  ruff: {runs-on: ubuntu-latest}
  tests:
    name: test
    runs-on: ubuntu-latest
  versions:
    strategy: {matrix: {python: ["3.11", "3.12"]}}
    runs-on: ubuntu-latest
  ci-gate:
    if: always()
    needs: [ruff, tests]
    runs-on: ubuntu-latest
"""


def test_check_names_are_job_names_or_ids_and_skip_matrix_jobs() -> None:
    assert pull_request_check_names(CI) == {"ruff", "test", "ci-gate"}


@pytest.mark.parametrize("on", ["pull_request", "[push, pull_request]", "{pull_request: {branches: [main]}}"])
def test_every_form_of_a_pull_request_trigger_counts(on: str) -> None:
    assert pull_request_check_names(f"on: {on}\njobs:\n  ci-gate: {{}}\n") == {"ci-gate"}


@pytest.mark.parametrize(
    "text",
    [
        "on: {push: {branches: [main]}}\njobs:\n  ci-gate: {}\n",  # never runs on a pull request
        "on: pull_request\n",  # no jobs
        "on: [pull_request\n",  # not valid YAML
        "- just a list\n",
    ],
)
def test_workflows_that_report_nothing_on_pull_requests(text: str) -> None:
    assert pull_request_check_names(text) == set()


CODEOWNERS = """\
# Default owner for everything
*                     @will
/docs/                @writers
.github/              @will   # CI and this file
/src/generated/*.py
"""


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("README.md", ["@will"]),
        ("docs/guide/intro.md", ["@writers"]),
        (".github/workflows/ci.yml", ["@will"]),
        (".github/CODEOWNERS", ["@will"]),
        ("src/generated/models.py", []),  # last match wins, and names nobody
        ("src/generated/sub/models.py", ["@will"]),  # * doesn't cross directories
    ],
)
def test_owners_follow_the_last_matching_line(path: str, expected: list[str]) -> None:
    assert owners(CODEOWNERS, path) == expected


def test_an_unanchored_name_matches_at_any_depth_and_an_anchored_one_only_at_the_root() -> None:
    assert owners("workflows @will\n", ".github/workflows/ci.yml") == ["@will"]
    assert owners("/workflows/ @will\n", ".github/workflows/ci.yml") == []
    assert owners("/.github/workflows/*.yml @will\n", ".github/workflows/ci.yml") == ["@will"]


def test_no_codeowners_line_means_no_owner() -> None:
    assert owners("# nothing yet\n", ".github/workflows/ci.yml") == []
