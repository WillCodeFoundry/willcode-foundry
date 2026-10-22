"""foundry protect check / apply, end to end against a fake GitHub."""

import shutil
from pathlib import Path

import pytest

from foundry import cli, github
from tests.fake_github import FakeGitHub

REPO_ROOT = Path(__file__).parents[1]

CONFIG = """\
name: test
projects:
  store: {url: "git@github.com:o/store.git"}
  site: {url: "git@github.com:o/site.git"}
roles: {}
"""

RULESETS = """\
rulesets:
  - name: agent-branches
    target: branch
    enforcement: active
    bypass_actors: [{actor_type: RepositoryRole, actor_id: 5, bypass_mode: always}]
    conditions: {ref_name: {include: ["refs/heads/task/**"], exclude: []}}
    rules: [{type: deletion}, {type: non_fast_forward}]
"""

RULESET = {
    "name": "agent-branches",
    "target": "branch",
    "enforcement": "active",
    "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}],
    "conditions": {"ref_name": {"include": ["refs/heads/task/**"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
}

CI = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    policy_dir = tmp_path / "config" / "repo-policy"
    shutil.copytree(REPO_ROOT / "config" / "repo-policy", policy_dir)
    (policy_dir / "rulesets.yaml").write_text(RULESETS)
    monkeypatch.chdir(tmp_path)
    fake = FakeGitHub()
    for slug in ("o/store", "o/site"):
        fake.files[slug] = {".github/CODEOWNERS": "* @WillCodeCo\n", ".github/workflows/ci.yml": CI}
    monkeypatch.setattr("foundry.commands.protect.GitHub", lambda: github.GitHub(fake))
    return fake


def test_check_passes_when_every_project_matches(fake: FakeGitHub, capsys: pytest.CaptureFixture[str]) -> None:
    fake.add("o/store", RULESET)
    fake.add("o/site", RULESET)

    assert cli.main(["protect", "check"]) == 0
    out = capsys.readouterr().out
    assert out == "site (o/site)\n  conforms\nstore (o/store)\n  conforms\n"  # deviations only


def test_check_fails_and_shows_the_diff(fake: FakeGitHub, capsys: pytest.CaptureFixture[str]) -> None:
    fake.add("o/store", {**RULESET, "rules": [{"type": "deletion"}]})
    fake.files["o/store"][".github/CODEOWNERS"] = "* @someone\n"

    assert cli.main(["protect", "check", "store"]) == 1
    out = capsys.readouterr().out
    assert "differs  ruleset agent-branches" in out
    assert "+++ ruleset agent-branches (repo policy)" in out
    assert "differs  .github/workflows/ci.yml" not in out and "conforms" not in out
    assert '+      "type": "non_fast_forward"' in out
    assert "differs  .github/CODEOWNERS" in out
    assert "           -* @someone\n           +* @WillCodeCo" in out


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
    assert "store (o/store)\n  conforms" in out


def test_apply_creates_and_updates_rulesets_until_check_passes(
    fake: FakeGitHub, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.add("o/store", {**RULESET, "enforcement": "evaluate"})

    assert cli.main(["protect", "apply"]) == 0
    out = capsys.readouterr().out
    assert "store (o/store)\n  updated  ruleset agent-branches\n  conforms" in out
    assert "site (o/site)\n  created  ruleset agent-branches\n  conforms" in out
    assert cli.main(["protect", "check"]) == 0


def test_apply_shows_project_files_but_never_writes_them(fake: FakeGitHub, capsys: pytest.CaptureFixture[str]) -> None:
    del fake.files["o/store"][".github/CODEOWNERS"]

    assert cli.main(["protect", "apply", "store"]) == 1
    assert "differs  .github/CODEOWNERS" in capsys.readouterr().out
    assert [call for call in fake.calls if call[0] in {"POST", "PUT"}] == [("POST", "repos/o/store/rulesets")]


def test_unknown_project_is_an_error(fake: FakeGitHub, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["protect", "check", "nope"]) == 1
    assert "unknown project 'nope'" in capsys.readouterr().err
