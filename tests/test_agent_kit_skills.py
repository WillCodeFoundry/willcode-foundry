"""The agent kit's skills as installed: what skills.lock lists is there at its commit, with its licence, and
every role's skill list names installed skills, including those its skills call. Reads the real kit; no
network."""

import re
from pathlib import Path

import pytest

from foundry import config, paths, skills

REPO_ROOT = Path(__file__).parents[1]
SKILLS_DIR = paths.skills_dir(REPO_ROOT)
ROLES_DIR = paths.agent_kit_dir(REPO_ROOT) / "roles"
LOCK = skills.load_lock(SKILLS_DIR / skills.LOCK_FILE)
ROLE_NAMES = sorted(config.load(paths.config_path(REPO_ROOT)).roles)
SKILL_CALL = re.compile(r'call the Skill tool with "([^"]+)"')


def role_skills(role: str) -> list[str]:
    """The names in roles/<role>/skills, as bin/link-skills reads them."""
    lines = (ROLES_DIR / role / "skills").read_text().splitlines()
    return [name for line in lines if (name := line.partition("#")[0].strip())]


def installed_skills() -> list[Path]:
    return sorted(path.parent for path in SKILLS_DIR.glob("*/SKILL.md"))


@pytest.mark.parametrize("name", sorted(LOCK.skills))
def test_every_locked_skill_is_installed_at_the_locks_commit(name: str) -> None:
    skill_md = SKILLS_DIR / name / "SKILL.md"
    assert skill_md.is_file(), f"{name} is in {skills.LOCK_FILE} but not installed: run foundry skills update"
    source = skills.source_metadata(skill_md.read_text())
    assert isinstance(source, dict)
    assert source["commit"] == LOCK.commit, f"{name} was installed from another commit: run foundry skills update"


def test_the_sources_licence_is_there() -> None:
    assert (SKILLS_DIR / LOCK.license_copy).is_file()


def test_every_role_in_the_config_has_a_skills_list() -> None:
    assert [role for role in ROLE_NAMES if not (ROLES_DIR / role / "skills").is_file()] == []


@pytest.mark.parametrize("role", ROLE_NAMES)
def test_a_roles_skills_are_installed(role: str) -> None:
    missing = [name for name in role_skills(role) if not (SKILLS_DIR / name / "SKILL.md").is_file()]
    assert missing == [], f"roles/{role}/skills lists skills agent-kit/skills/ doesn't have"


@pytest.mark.parametrize("role", ROLE_NAMES)
def test_every_skill_a_roles_skills_call_is_on_its_list(role: str) -> None:
    listed = role_skills(role)
    called = {
        (name, called_name)
        for name in listed
        for path in sorted((SKILLS_DIR / name).rglob("*.md"))
        for called_name in SKILL_CALL.findall(path.read_text())
    }
    assert sorted((name, called) for name, called in called if called not in listed) == [], (
        f"a skill on roles/{role}/skills calls one that isn't on it"
    )


@pytest.mark.parametrize("skill_dir", installed_skills(), ids=lambda path: path.name)
def test_no_skill_is_a_placeholder(skill_dir: Path) -> None:
    text = (skill_dir / "SKILL.md").read_text()
    body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.DOTALL)
    assert body.strip() not in ("", "TODO"), f"{skill_dir.name}'s SKILL.md is a placeholder"
