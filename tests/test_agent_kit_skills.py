"""The agent kit's skills as committed: what skills.lock lists is there, attributed to the lock's commit, with
upstream's licence and no merge left half-done; and every role's skill list names installed skills, including
those its skills call. Reads the real kit; no network."""

import re
from pathlib import Path

import pytest
import yaml

from foundry import config, paths

REPO_ROOT = Path(__file__).parents[1]
SKILLS_DIR = paths.agent_kit_dir(REPO_ROOT) / "skills"
ROLES_DIR = paths.agent_kit_dir(REPO_ROOT) / "roles"
ROLE_NAMES = sorted(config.load(paths.config_path(REPO_ROOT)).roles)
SKILL_CALL = re.compile(r'call the Skill tool with "([^"]+)"')
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def lock_lines() -> dict[str, list[list[str]]]:
    """skills.lock's lines by their first word, as scripts/update-skills reads them."""
    lines: dict[str, list[list[str]]] = {}
    for line in (SKILLS_DIR / "skills.lock").read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            kind, *values = line.split()
            lines.setdefault(kind, []).append(values)
    return lines


LOCK = lock_lines()
LOCKED_SKILLS = [name for name, _ in LOCK["skill"]]


def role_skills(role: str) -> list[str]:
    """The names in roles/<role>/skills, as bin/link-skills reads them."""
    lines = (ROLES_DIR / role / "skills").read_text().splitlines()
    return [name for line in lines if (name := line.partition("#")[0].strip())]


def installed_skills() -> list[Path]:
    return sorted(path.parent for path in SKILLS_DIR.glob("*/SKILL.md"))


def test_the_lock_names_one_upstream_commit_and_its_licence() -> None:
    assert [len(LOCK["repo"]), len(LOCK["commit"]), len(LOCK["license"])] == [1, 1, 1]
    assert re.fullmatch(r"[0-9a-f]{40}", LOCK["commit"][0][0])
    assert (SKILLS_DIR / LOCK["license"][0][1]).is_file()


@pytest.mark.parametrize("name", LOCKED_SKILLS)
def test_every_locked_skill_is_installed_and_attributed_to_the_locks_commit(name: str) -> None:
    skill_md = SKILLS_DIR / name / "SKILL.md"
    assert skill_md.is_file(), f"{name} is in skills.lock but not in agent-kit/skills/"
    match = FRONTMATTER.match(skill_md.read_text())
    assert match, f"{name}'s SKILL.md has no frontmatter"
    source = yaml.safe_load(match[1])["metadata"]["source"]
    assert source["commit"] == LOCK["commit"][0][0], f"{name}'s metadata.source.commit isn't skills.lock's commit"
    assert not (SKILLS_DIR / name / "agents").exists()


@pytest.mark.parametrize("skill_dir", installed_skills(), ids=lambda path: path.name)
def test_no_merge_conflict_is_left_in_a_skill(skill_dir: Path) -> None:
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file():
            text = path.read_text()
            assert not re.search(r"^(<<<<<<<|>>>>>>>) ", text, re.MULTILINE), f"conflict markers in {path}"


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
    body = FRONTMATTER.sub("", text)
    assert body.strip() not in ("", "TODO"), f"{skill_dir.name}'s SKILL.md is a placeholder"
