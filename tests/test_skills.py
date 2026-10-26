"""foundry skills update, against a local "upstream" repository standing in for GitHub."""

import subprocess
from pathlib import Path

import pytest

from foundry.commands import skills
from foundry.errors import FoundryError

UPSTREAM_SKILL = "---\nname: tdd\n---\n\nFirst.\nSecond.\nThird.\n"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def commit_all(cwd: Path, message: str) -> str:
    git(cwd, "add", "-A")
    git(cwd, "commit", "-qm", message)
    return git(cwd, "rev-parse", "HEAD")


@pytest.fixture(autouse=True)
def git_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key, value in {"user.name": "t", "user.email": "t@t", "commit.gpgsign": "false"}.items():
        git(tmp_path, "config", "--global", key, value)


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """mattpocock/skills, as far as the update needs it: a skill, its agents/ folder, and the licence."""
    repo = tmp_path / "upstream"
    skill = repo / "skills" / "engineering" / "tdd"
    (skill / "agents").mkdir(parents=True)
    (skill / "SKILL.md").write_text(UPSTREAM_SKILL)
    (skill / "agents" / "codex.yaml").write_text("x: 1\n")
    (repo / "LICENSE").write_text("MIT, first\n")
    git(tmp_path, "init", "-q", str(repo))
    commit_all(repo, "first")
    return repo


def copied_skill_md(commit: str, body: str) -> str:
    return (
        "---\nname: tdd\nmetadata:\n  source:\n    repo: mattpocock/skills\n    path: skills/engineering/tdd\n"
        f"    commit: {commit}\n    author: Matt Pocock\n  adapted: for the foundry\n---\n{body}"
    )


@pytest.fixture
def foundry_root(tmp_path: Path, upstream: Path) -> Path:
    """A foundry whose kit copied tdd at upstream's first commit and edited its first line, and has its own skill."""
    root = tmp_path / "foundry"
    (root / "config").mkdir(parents=True)
    (root / "config" / "foundry.yaml").write_text("name: t\n")
    skills_dir = root / "agent-kit" / "skills"
    (skills_dir / "tdd").mkdir(parents=True)
    first = git(upstream, "rev-parse", "HEAD")
    (skills_dir / "tdd" / "SKILL.md").write_text(copied_skill_md(first, "\nFirst, for the foundry.\nSecond.\nThird.\n"))
    (skills_dir / "own").mkdir()
    (skills_dir / "own" / "SKILL.md").write_text("---\nname: own\n---\n\nOurs.\n")
    git(tmp_path, "init", "-q", str(root))
    commit_all(root, "init")
    return root


def update(foundry_root: Path, upstream: Path, commit: str = "HEAD") -> tuple[list[str], list[str]]:
    """(the lines it reported, the skills left with conflicts)."""
    reported: list[str] = []
    conflicted = skills.update(foundry_root, commit, url_for=lambda repo: str(upstream), report=reported.append)
    return reported, conflicted


def test_upstreams_changes_merge_with_the_foundrys_and_the_commit_is_recorded(foundry_root, upstream) -> None:
    skill_md = upstream / "skills" / "engineering" / "tdd" / "SKILL.md"
    skill_md.write_text(UPSTREAM_SKILL.replace("Third.", "Third, improved."))
    (upstream / "skills" / "engineering" / "tdd" / "agents" / "codex.yaml").write_text("x: 2\n")
    (upstream / "skills" / "engineering" / "tdd" / "NEW.md").write_text("New.\n")
    (upstream / "LICENSE").write_text("MIT, second\n")
    second = commit_all(upstream, "second")

    reported, conflicted = update(foundry_root, upstream)

    skill_dir = foundry_root / "agent-kit" / "skills" / "tdd"
    assert (reported, conflicted) == ([f"tdd: updated to {second[:12]}"], [])
    assert (skill_dir / "SKILL.md").read_text() == copied_skill_md(
        second, "\nFirst, for the foundry.\nSecond.\nThird, improved.\n"
    )
    assert (skill_dir / "NEW.md").read_text() == "New.\n"
    assert not (skill_dir / "agents").exists()
    assert (foundry_root / "agent-kit" / "skills" / "LICENSE-mattpocock").read_text() == "MIT, second\n"


def test_a_skill_already_up_to_date_is_left_alone(foundry_root, upstream) -> None:
    before = git(foundry_root, "status", "--porcelain")

    reported, _ = update(foundry_root, upstream)

    assert reported == [f"tdd: already at {git(upstream, 'rev-parse', 'HEAD')[:12]}"]
    assert git(foundry_root, "status", "--porcelain") == before == ""


def test_a_line_both_sides_changed_is_left_as_a_conflict(foundry_root, upstream) -> None:
    skill_md = upstream / "skills" / "engineering" / "tdd" / "SKILL.md"
    skill_md.write_text(UPSTREAM_SKILL.replace("First.", "First, upstream's way."))
    second = commit_all(upstream, "second")

    _, conflicted = update(foundry_root, upstream)

    assert conflicted == ["tdd"]
    text = (foundry_root / "agent-kit" / "skills" / "tdd" / "SKILL.md").read_text()
    assert "<<<<<<<" in text and f"    commit: {second}\n" in text


def test_a_given_commit_is_the_one_updated_to(foundry_root, upstream) -> None:
    skill_md = upstream / "skills" / "engineering" / "tdd" / "SKILL.md"
    skill_md.write_text(UPSTREAM_SKILL.replace("Third.", "Third, improved."))
    second = commit_all(upstream, "second")
    skill_md.write_text(UPSTREAM_SKILL.replace("Third.", "Third, improved twice."))
    commit_all(upstream, "third")

    assert update(foundry_root, upstream, second)[0] == [f"tdd: updated to {second[:12]}"]
    assert "Third, improved.\n" in (foundry_root / "agent-kit" / "skills" / "tdd" / "SKILL.md").read_text()


def test_a_source_without_its_commit_is_reported(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\nmetadata:\n  source:\n    repo: o/r\n    path: p\n---\n")

    with pytest.raises(FoundryError, match=r"metadata\.source has no commit"):
        skills.read_source(skill_md)


def test_the_kits_copied_skills_all_have_a_source() -> None:
    """Every skill this repository copied records where from; its own skill doesn't."""
    skills_dir = Path(__file__).parents[1] / "agent-kit" / "skills"
    sources = {path.parent.name: skills.read_source(path) for path in skills_dir.glob("*/SKILL.md")}

    assert sorted(name for name, source in sources.items() if source is None) == ["git-conventions"]
    assert {source.repo for source in sources.values() if source is not None} == {"mattpocock/skills"}


def test_skills_updated_before_a_failure_are_still_reported(foundry_root: Path, upstream: Path, tmp_path: Path) -> None:
    """A later skill's upstream can't be fetched: the earlier one is already changed on disk, and says so."""
    skill_md = upstream / "skills" / "engineering" / "tdd" / "SKILL.md"
    skill_md.write_text(UPSTREAM_SKILL.replace("Third.", "Third, improved."))
    second = commit_all(upstream, "second")
    (foundry_root / "agent-kit" / "skills" / "zz").mkdir()
    (foundry_root / "agent-kit" / "skills" / "zz" / "SKILL.md").write_text(
        copied_skill_md("0" * 40, "\nOther.\n").replace("mattpocock/skills", "other/skills")
    )
    reported: list[str] = []
    urls = {"mattpocock/skills": str(upstream), "other/skills": str(tmp_path / "missing")}

    with pytest.raises(FoundryError, match="git fetch"):
        skills.update(foundry_root, url_for=urls.__getitem__, report=reported.append)

    assert reported == [f"tdd: updated to {second[:12]}"]
