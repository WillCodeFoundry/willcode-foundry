"""scripts/update-skills against a throwaway upstream repository and a throwaway foundry repository: upstream's
changes are merged into the kit's edited copies of its skills, three-way, and the new commit is recorded."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

UPDATE_SKILLS = Path(__file__).parents[1] / "scripts" / "update-skills"

UPSTREAM_SKILL = """\
---
name: tdd
description: Use when the user wants tests first.
---

# TDD

Confirm the seams with the user.

## Rules

Red before green.
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def write(root: Path, files: dict[str, str]) -> None:
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture(autouse=True)
def git_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[user]\n\tname = t\n\temail = t@t\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """The source repository: one skill, its Codex metadata, and a licence."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "--quiet")
    write(
        upstream,
        {
            "LICENSE": "MIT License, v1\n",
            "skills/engineering/tdd/SKILL.md": UPSTREAM_SKILL,
            "skills/engineering/tdd/agents/openai.yaml": "interface: {}\n",
        },
    )
    commit_all(upstream, "v1")
    return upstream


@pytest.fixture
def foundry(tmp_path: Path, upstream: Path) -> Path:
    """A foundry repository whose kit has tdd copied from upstream's first commit, then edited."""
    foundry = tmp_path / "foundry"
    foundry.mkdir()
    git(foundry, "init", "--quiet")
    (foundry / "scripts").mkdir()
    shutil.copy(UPDATE_SKILLS, foundry / "scripts" / "update-skills")
    first = git(upstream, "rev-parse", "HEAD")
    edited = UPSTREAM_SKILL.replace(
        "---\n\n# TDD",
        f"metadata:\n  source:\n    repo: upstream/skills\n    commit: {first}\n---\n\n# TDD",
    ).replace("Confirm the seams with the user.", "Take the seams from TASK.md.")
    write(
        foundry,
        {
            "agent-kit/skills/skills.lock": (
                "# where the kit's copied skills come from\n"
                f"repo file://{upstream}\n"
                f"commit {first}\n"
                "license LICENSE LICENSE-upstream\n"
                "\n"
                "skill tdd skills/engineering/tdd\n"
            ),
            "agent-kit/skills/LICENSE-upstream": "MIT License, v1\n",
            "agent-kit/skills/tdd/SKILL.md": edited,
        },
    )
    commit_all(foundry, "copy tdd")
    return foundry


def update_skills(foundry: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(foundry / "scripts" / "update-skills"), *args],
        cwd=foundry / "agent-kit",  # works from anywhere in the repository
        env=os.environ,
        capture_output=True,
        text=True,
        check=False,
    )


def skill_md(foundry: Path) -> str:
    return (foundry / "agent-kit" / "skills" / "tdd" / "SKILL.md").read_text()


def lock(foundry: Path) -> str:
    return (foundry / "agent-kit" / "skills" / "skills.lock").read_text()


def test_upstreams_changes_are_merged_into_the_edited_copy(foundry, upstream) -> None:
    first = git(upstream, "rev-parse", "HEAD")
    write(
        upstream,
        {
            "LICENSE": "MIT License, v2\n",
            "skills/engineering/tdd/SKILL.md": UPSTREAM_SKILL.replace("Red before green.", "Red, then green."),
            "skills/engineering/tdd/tests.md": "# Good tests\n",
            "skills/engineering/tdd/agents/openai.yaml": "interface: {changed: true}\n",
        },
    )
    second = commit_all(upstream, "v2")

    result = update_skills(foundry)

    assert result.returncode == 0, result.stderr
    merged = skill_md(foundry)
    assert "Take the seams from TASK.md." in merged  # the foundry's edit
    assert "Red, then green." in merged  # upstream's change
    assert f"commit: {second}" in merged and first not in merged
    assert f"commit {second}\n" in lock(foundry) and first not in lock(foundry)
    assert (foundry / "agent-kit/skills/tdd/tests.md").read_text() == "# Good tests\n"
    assert not (foundry / "agent-kit/skills/tdd/agents").exists()
    assert (foundry / "agent-kit/skills/LICENSE-upstream").read_text() == "MIT License, v2\n"
    assert f"updated tdd to {second[:12]}" in result.stdout


def test_a_change_on_a_line_the_foundry_edited_is_left_as_a_conflict(foundry, upstream) -> None:
    write(
        upstream,
        {"skills/engineering/tdd/SKILL.md": UPSTREAM_SKILL.replace("with the user.", "with the user, in writing.")},
    )
    second = commit_all(upstream, "v2")

    result = update_skills(foundry)

    assert result.returncode == 1
    assert "conflicts in tdd" in result.stderr
    merged = skill_md(foundry)
    assert "<<<<<<< ours\nTake the seams from TASK.md.\n=======\n" in merged
    assert "Confirm the seams with the user, in writing.\n>>>>>>> theirs" in merged
    assert f"commit {second}\n" in lock(foundry)  # recorded, so running again doesn't apply it twice
    assert "UU agent-kit/skills/tdd/SKILL.md" in git(foundry, "status", "--short")


def test_a_named_commit_is_used_instead_of_upstreams_latest(foundry, upstream) -> None:
    write(upstream, {"skills/engineering/tdd/tests.md": "# v2\n"})
    second = commit_all(upstream, "v2")
    write(upstream, {"skills/engineering/tdd/tests.md": "# v3\n"})
    commit_all(upstream, "v3")

    result = update_skills(foundry, second)

    assert result.returncode == 0, result.stderr
    assert (foundry / "agent-kit/skills/tdd/tests.md").read_text() == "# v2\n"
    assert f"commit {second}\n" in lock(foundry)


def test_nothing_changes_when_already_at_upstreams_commit(foundry) -> None:
    before = git(foundry, "rev-parse", "HEAD:agent-kit/skills")

    result = update_skills(foundry)

    assert result.returncode == 0, result.stderr
    assert "already at" in result.stdout
    assert git(foundry, "status", "--short") == ""
    assert git(foundry, "rev-parse", "HEAD:agent-kit/skills") == before


def test_uncommitted_changes_to_the_skills_are_refused(foundry, upstream) -> None:
    write(upstream, {"skills/engineering/tdd/tests.md": "# v2\n"})
    commit_all(upstream, "v2")
    (foundry / "agent-kit/skills/tdd/SKILL.md").write_text("half-edited\n")

    result = update_skills(foundry)

    assert result.returncode == 1
    assert "uncommitted changes in agent-kit/skills" in result.stderr
    assert skill_md(foundry) == "half-edited\n"


def test_an_unknown_line_in_the_lock_is_refused(foundry) -> None:
    (foundry / "agent-kit/skills/skills.lock").write_text(lock(foundry) + "skil typo skills/x\n")
    commit_all(foundry, "typo")

    result = update_skills(foundry)

    assert result.returncode == 1
    assert "skills.lock: don't know 'skil typo skills/x'" in result.stderr
