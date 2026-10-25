"""agent-kit/bin/link-skills, with a temporary HOME and a temporary kit: it links exactly the role's skills
into ~/.claude/skills/, removes links no longer listed, and never touches real folders. And the real kit's
role lists: link-skills can't see that a listed skill calls one the role doesn't have."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

AGENT_KIT = Path(__file__).parents[2] / "agent-kit"
LINK_SKILLS = AGENT_KIT / "bin" / "link-skills"


@pytest.fixture
def kit(tmp_path: Path) -> Path:
    """A kit with three skills and a dev role listing two of them."""
    kit = tmp_path / "kit"
    for name in ("tdd", "pr", "grilling"):
        (kit / "skills" / name).mkdir(parents=True)
        (kit / "skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    (kit / "roles" / "dev").mkdir(parents=True)
    (kit / "roles" / "dev" / "skills").write_text("# the dev's skills\ntdd\n\n  pr  # bodies\n")
    (kit / "bin").mkdir()
    shutil.copy(LINK_SKILLS, kit / "bin" / "link-skills")
    return kit


@pytest.fixture
def home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def link_skills(kit: Path, home: Path, role: str = "dev") -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "AGENT_KIT_DIR": str(kit), "AGENT_ROLE": role}
    return subprocess.run([str(kit / "bin" / "link-skills")], env=env, capture_output=True, text=True, check=False)


def linked(home: Path) -> dict[str, str]:
    skills_dir = home / ".claude" / "skills"
    return {path.name: os.readlink(path) for path in sorted(skills_dir.iterdir()) if path.is_symlink()}


def test_exactly_the_listed_skills_are_linked(kit, home) -> None:
    result = link_skills(kit, home)

    assert result.returncode == 0, result.stderr
    assert linked(home) == {"pr": str(kit / "skills" / "pr"), "tdd": str(kit / "skills" / "tdd")}
    assert (home / ".claude" / "skills" / "tdd" / "SKILL.md").is_file()


def test_a_link_no_longer_listed_is_removed(kit, home) -> None:
    skills_dir = home / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "grilling").symlink_to(kit / "skills" / "grilling")
    (skills_dir / "gone").symlink_to(kit / "skills" / "gone")  # dangling: a skill since removed from the kit

    assert link_skills(kit, home).returncode == 0
    assert sorted(linked(home)) == ["pr", "tdd"]


def test_a_real_folder_is_left_alone(kit, home) -> None:
    own = home / ".claude" / "skills" / "mine"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("the agent's own\n")

    assert link_skills(kit, home).returncode == 0
    assert (own / "SKILL.md").read_text() == "the agent's own\n"
    assert not own.is_symlink()


def test_a_listed_skill_that_doesnt_exist_is_refused_by_name(kit, home) -> None:
    (kit / "roles" / "dev" / "skills").write_text("tdd\nmissing\n")

    result = link_skills(kit, home)

    assert result.returncode == 1
    assert "missing" in result.stderr and "SKILL.md" in result.stderr


def test_a_role_without_a_list_gets_no_skills(kit, home) -> None:
    skills_dir = home / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "tdd").symlink_to(kit / "skills" / "tdd")

    result = link_skills(kit, home, role="architect")

    assert result.returncode == 0, result.stderr
    assert linked(home) == {}


@pytest.mark.parametrize("role_list", sorted(AGENT_KIT.glob("roles/*/skills")), ids=lambda path: path.parent.name)
def test_every_skill_a_roles_skills_call_is_on_its_list(role_list: Path) -> None:
    listed = {name for line in role_list.read_text().splitlines() if (name := line.partition("#")[0].strip())}
    called = {
        (name, called_name)
        for name in sorted(listed)
        for path in sorted((AGENT_KIT / "skills" / name).rglob("*.md"))
        for called_name in re.findall(r'call the Skill tool with "([^"]+)"', path.read_text())
    }
    assert sorted((name, called) for name, called in called if called not in listed) == []
