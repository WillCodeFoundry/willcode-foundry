"""foundry protect check / apply, end to end against a fake GitHub."""

from pathlib import Path

import pytest

from foundry import cli, github
from tests.fake_github import FakeGitHub

CONFIG = """\
name: test
projects:
  store: {url: "git@github.com:o/store.git"}
  site: {url: "git@github.com:o/site.git"}
roles: {}
"""

PROTECTION = """\
rulesets:
  - name: agent-branches
    target: branch
    enforcement: active
    bypass_actors: []
    conditions: {ref_name: {include: ["refs/heads/task/**"], exclude: []}}
    rules: [{type: deletion}, {type: non_fast_forward}]
"""

RULESET = {
    "name": "agent-branches",
    "target": "branch",
    "enforcement": "active",
    "bypass_actors": [],
    "conditions": {"ref_name": {"include": ["refs/heads/task/**"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
}


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    (tmp_path / "config" / "github-protection.yaml").write_text(PROTECTION)
    monkeypatch.chdir(tmp_path)
    fake = FakeGitHub()
    monkeypatch.setattr("foundry.commands.protect.GitHub", lambda: github.GitHub(fake))
    return fake


def test_check_passes_when_every_project_matches(fake: FakeGitHub, capsys: pytest.CaptureFixture[str]) -> None:
    fake.add("o/store", RULESET)
    fake.add("o/site", RULESET)

    assert cli.main(["protect", "check"]) == 0
    assert capsys.readouterr().out.count("ok       agent-branches") == 2


def test_check_fails_and_says_what_is_wrong(fake: FakeGitHub, capsys: pytest.CaptureFixture[str]) -> None:
    fake.add("o/store", {**RULESET, "rules": [{"type": "deletion"}]})

    assert cli.main(["protect", "check"]) == 1
    out = capsys.readouterr().out
    assert "site (o/site)\n  missing  agent-branches" in out
    assert "store (o/store)\n  differs  agent-branches\n           rules[non_fast_forward]: missing" in out


def test_check_reports_a_repo_github_refuses_and_carries_on(
    fake: FakeGitHub, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.unavailable["o/site"] = (
        "Upgrade to GitHub Pro or make this repository public to enable this feature. (HTTP 403)"
    )
    fake.add("o/store", RULESET)

    assert cli.main(["protect", "check"]) == 1
    out = capsys.readouterr().out
    assert "site (o/site)\n  error    Upgrade to GitHub Pro" in out
    assert "store (o/store)\n  ok       agent-branches" in out


def test_check_only_the_named_projects(fake: FakeGitHub) -> None:
    fake.add("o/store", RULESET)

    assert cli.main(["protect", "check", "store"]) == 0
    assert {endpoint.split("/rulesets")[0] for _, endpoint in fake.calls} == {"repos/o/store"}


def test_dry_run_changes_nothing(fake: FakeGitHub, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["protect", "apply", "--dry-run", "store"]) == 1
    assert "would create agent-branches" in capsys.readouterr().out
    assert [method for method, _ in fake.calls] == ["GET"]


def test_apply_makes_check_pass(fake: FakeGitHub) -> None:
    fake.add("o/store", {**RULESET, "enforcement": "evaluate"})

    assert cli.main(["protect", "apply"]) == 0
    assert cli.main(["protect", "check"]) == 0


def test_unknown_project_is_an_error(fake: FakeGitHub, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["protect", "check", "nope"]) == 1
    assert "unknown project 'nope'" in capsys.readouterr().err
