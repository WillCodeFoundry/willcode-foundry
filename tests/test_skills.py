"""foundry skills update, against a local "upstream" repository standing in for GitHub."""

from pathlib import Path

import pytest

from agent_runtime.git import GitError
from foundry import cli
from foundry.commands import skills
from foundry.errors import FoundryError
from tests.conftest import git

pytestmark = pytest.mark.usefixtures("git_identity")

UPSTREAM_SKILL = "---\nname: tdd\n---\n\nFirst.\nSecond.\nThird.\n"


def commit_all(cwd: Path, message: str) -> str:
    git(cwd, "add", "-A")
    git(cwd, "commit", "-qm", message)
    return git(cwd, "rev-parse", "HEAD").stdout.strip()


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
    first = git(upstream, "rev-parse", "HEAD").stdout.strip()
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
    (upstream / "LICENSE").write_bytes("MIT, second, ©\r\n".encode())
    second = commit_all(upstream, "second")

    reported, conflicted = update(foundry_root, upstream)

    skill_dir = foundry_root / "agent-kit" / "skills" / "tdd"
    assert (reported, conflicted) == ([f"tdd: updated to {second[:12]}"], [])
    assert (skill_dir / "SKILL.md").read_text() == copied_skill_md(
        second, "\nFirst, for the foundry.\nSecond.\nThird, improved.\n"
    )
    assert (skill_dir / "NEW.md").read_text() == "New.\n"
    assert not (skill_dir / "agents").exists()
    licence = foundry_root / "agent-kit" / "skills" / "LICENSE-mattpocock-skills"
    assert licence.read_bytes() == "MIT, second, ©\r\n".encode()


def test_files_that_arent_utf_8_arrive_byte_for_byte(foundry_root, upstream) -> None:
    """Upstream's diff goes to git apply as bytes. A binary file's patch is ASCII anyway; a text file in another
    encoding puts its own bytes in the diff, which a diff read as text would mangle."""
    files = {"picture.bin": bytes(range(256)) + b"\x00\r\n\xff", "latin-1.md": "Café, à côté.\n".encode("latin-1")}
    for name, content in files.items():
        (upstream / "skills" / "engineering" / "tdd" / name).write_bytes(content)
    second = commit_all(upstream, "second")

    reported, conflicted = update(foundry_root, upstream)

    assert (reported, conflicted) == ([f"tdd: updated to {second[:12]}"], [])
    for name, content in files.items():
        assert (foundry_root / "agent-kit" / "skills" / "tdd" / name).read_bytes() == content, name


def test_a_skill_already_up_to_date_is_left_alone(foundry_root, upstream) -> None:
    before = git(foundry_root, "status", "--porcelain").stdout.strip()

    reported, _ = update(foundry_root, upstream)

    assert reported == [f"tdd: already at {git(upstream, 'rev-parse', 'HEAD').stdout.strip()[:12]}"]
    assert git(foundry_root, "status", "--porcelain").stdout.strip() == before == ""


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


def kit_status(foundry_root: Path) -> str:
    return git(foundry_root, "status", "--porcelain").stdout


def test_a_skill_with_uncommitted_changes_is_refused_before_anything_changes(foundry_root, upstream) -> None:
    """git apply --3way checks against the index: it would reject the whole patch, not merge into the edits."""
    skill_md = upstream / "skills" / "engineering" / "tdd" / "SKILL.md"
    skill_md.write_text(UPSTREAM_SKILL.replace("Third.", "Third, improved."))
    commit_all(upstream, "second")
    kit_skill_md = foundry_root / "agent-kit" / "skills" / "tdd" / "SKILL.md"
    kit_skill_md.write_text(kit_skill_md.read_text() + "An edit in progress.\n")
    before = kit_status(foundry_root)

    with pytest.raises(FoundryError, match=r"^tdd: agent-kit/skills/tdd has uncommitted changes; commit them"):
        update(foundry_root, upstream)

    assert kit_status(foundry_root) == before


def test_a_patch_git_rejects_is_an_error_and_the_commit_stays(foundry_root, upstream) -> None:
    """Upstream changes a file the foundry's copy removed: no conflict to resolve, so the commit mustn't move,
    or the next run would say it is up to date and upstream's change would be lost."""
    extra = upstream / "skills" / "engineering" / "tdd" / "EXTRA.md"
    extra.write_text("Extra.\n")
    second = commit_all(upstream, "second")
    kit_skill_md = foundry_root / "agent-kit" / "skills" / "tdd" / "SKILL.md"
    first = git(upstream, "rev-parse", "HEAD~").stdout.strip()
    kit_skill_md.write_text(kit_skill_md.read_text().replace(first, second))  # the copy left EXTRA.md out
    commit_all(foundry_root, "up to second, without EXTRA.md")
    extra.write_text("Extra, improved.\n")
    commit_all(upstream, "third")

    with pytest.raises(FoundryError, match=r"^tdd: git apply rejected upstream's changes"):
        update(foundry_root, upstream)

    assert kit_status(foundry_root) == ""


def test_spaces_after_the_recorded_commit_dont_stop_it_moving(foundry_root, upstream) -> None:
    kit_skill_md = foundry_root / "agent-kit" / "skills" / "tdd" / "SKILL.md"
    first = git(upstream, "rev-parse", "HEAD").stdout.strip()
    kit_skill_md.write_text(kit_skill_md.read_text().replace(f"commit: {first}\n", f"commit: {first}  \n"))
    commit_all(foundry_root, "trailing spaces")
    skill_md = upstream / "skills" / "engineering" / "tdd" / "SKILL.md"
    skill_md.write_text(UPSTREAM_SKILL.replace("Third.", "Third, improved."))
    second = commit_all(upstream, "second")

    update(foundry_root, upstream)

    assert f"    commit: {second}\n" in kit_skill_md.read_text()


def test_upstream_without_a_licence_changes_nothing(foundry_root, upstream) -> None:
    (upstream / "LICENSE").unlink()
    skill_md = upstream / "skills" / "engineering" / "tdd" / "SKILL.md"
    skill_md.write_text(UPSTREAM_SKILL.replace("Third.", "Third, improved."))
    commit_all(upstream, "second")

    with pytest.raises(GitError, match=r"^git show .*:LICENSE failed"):
        update(foundry_root, upstream)

    assert kit_status(foundry_root) == ""


def test_skills_from_one_repository_reach_one_commit_while_upstream_moves(foundry_root, upstream) -> None:
    """Upstream is resolved once per repository: a commit landing upstream mid-run doesn't split the skills."""
    review = upstream / "skills" / "engineering" / "review"
    review.mkdir()
    (review / "SKILL.md").write_text("---\nname: review\n---\n\nLook.\n")
    second = commit_all(upstream, "second")
    kit_review = foundry_root / "agent-kit" / "skills" / "review"
    kit_review.mkdir()
    (kit_review / "SKILL.md").write_text(
        copied_skill_md(second, "\nLook.\n").replace("skills/engineering/tdd", "skills/engineering/review")
    )
    commit_all(foundry_root, "copy review")
    (review / "SKILL.md").write_text("---\nname: review\n---\n\nLook closely.\n")
    third = commit_all(upstream, "third")
    landed: list[str] = []

    def url_for(repo: str) -> str:
        """Each lookup lands another commit upstream, after the first."""
        if landed:
            (upstream / "NEWS").write_text(f"{len(landed)}\n")
            landed.append(commit_all(upstream, "moved"))
        else:
            landed.append(third)
        return str(upstream)

    skills.update(foundry_root, url_for=url_for)

    for name in ("review", "tdd"):
        assert f"    commit: {third}\n" in (foundry_root / "agent-kit" / "skills" / name / "SKILL.md").read_text(), name


def test_each_copied_skill_names_its_repositorys_licence() -> None:
    """The licence update writes LICENSE-<owner>-<repo> beside the skills; each copied skill points at it."""
    skills_dir = Path(__file__).parents[1] / "agent-kit" / "skills"
    for skill_md in skills_dir.glob("*/SKILL.md"):
        if (source := skills.read_source(skill_md)) is not None:
            licence = f"LICENSE-{source.repo.replace('/', '-')}"
            assert f"(see ../{licence})" in skill_md.read_text(), skill_md
            assert (skills_dir / licence).is_file()


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
    commit_all(foundry_root, "copy zz")
    reported: list[str] = []
    urls = {"mattpocock/skills": str(upstream), "other/skills": str(tmp_path / "missing")}

    with pytest.raises(GitError, match=r"^git fetch --quiet --no-tags .*missing"):
        skills.update(foundry_root, url_for=urls.__getitem__, report=reported.append)

    assert reported == [f"tdd: updated to {second[:12]}"]


def test_skills_update_without_git_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, in this repository, with no git on PATH: an error line, not a traceback."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(Path(__file__).parents[1])
    monkeypatch.setenv("PATH", str(empty))

    assert cli.main(["skills", "update"]) == 1
    assert capsys.readouterr().err == "error: git not found in PATH\n"
