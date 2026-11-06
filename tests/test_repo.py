"""foundry repo check: its report, its arguments, and end to end through cli.main."""

import base64
import json
import os
from pathlib import Path

import pytest

from foundry import cli
from foundry.commands.repo import report
from foundry.config import Project
from foundry.repo_policy import Deviation, ProjectCheck, RulesetAction, RulesetChange

STORE = Project(name="store", url="git@github.com:o/store.git")


# --- report ---------------------------------------------------------------------


def test_a_conforming_repository() -> None:
    assert report(STORE, ProjectCheck([], [])) == ["store (o/store)", "  conforms"]


def test_what_fix_changed_comes_before_the_result() -> None:
    changes = [
        RulesetChange("agent-branches", RulesetAction.CREATED),
        RulesetChange("tags", RulesetAction.UPDATED),
    ]
    assert report(STORE, ProjectCheck(changes, [])) == [
        "store (o/store)",
        "  created  ruleset agent-branches",
        "  updated  ruleset tags",
        "  conforms",
    ]


def test_each_deviation_with_its_diff_indented() -> None:
    deviation = Deviation(subject=".github/CODEOWNERS", diff="--- a\n+++ b\n-* @someone\n+* @will\n")
    assert report(STORE, ProjectCheck([], [deviation])) == [
        "store (o/store)",
        "  differs  .github/CODEOWNERS",
        "           --- a",
        "           +++ b",
        "           -* @someone",
        "           +* @will",
    ]


def test_an_error_follows_the_changes_made_before_it() -> None:
    changes = [RulesetChange("agent-branches", RulesetAction.CREATED)]
    assert report(STORE, ProjectCheck(changes, [], error="boom (HTTP 502)")) == [
        "store (o/store)",
        "  created  ruleset agent-branches",
        "  error    boom (HTTP 502)",
    ]


# --- arguments ------------------------------------------------------------------


def test_fix_and_project_names_parse() -> None:
    args = cli.build_parser().parse_args(["repo", "check", "--fix", "store"])
    assert (args.fix, args.project_names) == (True, ["store"])
    assert cli.build_parser().parse_args(["repo", "check"]).fix is False


def test_a_project_whose_url_is_not_githubs_has_no_repo_in_its_header() -> None:
    elsewhere = Project(name="elsewhere", url="https://gitlab.com/o/p.git")
    assert report(elsewhere, ProjectCheck([], [], error="not GitHub")) == ["elsewhere", "  error    not GitHub"]


# --- end to end -----------------------------------------------------------------

CI_GATE = "on: push\njobs:\n  ci-gate: {runs-on: ubuntu-latest}\n"
CODEOWNERS = "* @o\n"


def test_check_prints_each_project_s_result_and_exits_1_unless_all_conform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, in a foundry of its own, with a stand-in for gh on PATH: store's repository
    has exactly the repo policy, and elsewhere's URL isn't GitHub's."""
    foundry_root = tmp_path / "foundry"
    policy_dir = foundry_root / "config" / "repo-policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "rulesets.yaml").write_text("rulesets: []\n")
    (policy_dir / "CODEOWNERS").write_text(CODEOWNERS)
    (policy_dir / "ci-gate.yml").write_text(CI_GATE)
    (foundry_root / "config" / "foundry.yaml").write_text(
        "name: f\nprojects:\n"
        "  store: {url: 'git@github.com:o/store.git'}\n"
        "  elsewhere: {url: 'https://gitlab.com/o/p.git'}\n"
        "roles: {}\n"
    )
    responses = {
        "repos/o/store/rulesets?per_page=100&includes_parents=false": [],
        "repos/o/store/contents/.github/CODEOWNERS": {"type": "file", "content": base64.b64encode(CODEOWNERS.encode())},
        "repos/o/store/contents/.github/workflows/ci.yml": {
            "type": "file",
            "content": base64.b64encode(CI_GATE.encode()),
        },
    }
    cases = "".join(
        f"  '{endpoint}') echo '{json.dumps(response, default=bytes.decode)}' ;;\n"
        for endpoint, response in responses.items()
    )
    gh = tmp_path / "bin" / "gh"
    gh.parent.mkdir()
    gh.write_text(f'#!/bin/sh\ncase "$4" in\n{cases}  *) echo "unexpected: $*" >&2; exit 1 ;;\nesac\n')
    gh.chmod(0o755)
    monkeypatch.chdir(foundry_root)
    monkeypatch.setenv("PATH", f"{gh.parent}:{os.environ['PATH']}")

    assert cli.main(["repo", "check", "store"]) == 0
    assert capsys.readouterr() == ("store (o/store)\n  conforms\n", "")

    assert cli.main(["repo", "check"]) == 1
    assert capsys.readouterr() == (
        "elsewhere\n"
        "  error    'https://gitlab.com/o/p.git' is not a GitHub repository URL\n"
        "store (o/store)\n"
        "  conforms\n",
        "",
    )
