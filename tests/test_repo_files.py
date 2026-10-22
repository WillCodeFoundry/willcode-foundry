import pytest

from foundry.repo_files import codeowners_lines, pull_request_check_names

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


def test_codeowners_lines_keep_patterns_and_owners_and_drop_comments() -> None:
    text = "# Default owner\n*  @will   # everything\n\n/docs/ @will @org/writers a@b.c\n/generated/\n"
    assert codeowners_lines(text) == [
        ("*", ["@will"]),
        ("/docs/", ["@will", "@org/writers", "a@b.c"]),
        ("/generated/", []),
    ]
