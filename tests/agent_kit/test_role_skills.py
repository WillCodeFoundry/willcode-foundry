"""Each role's skills, agent-kit/roles/<role>/skills/: links that session-init links as ~/.claude/skills.
Claude Code skips a broken link without a word, and can't tell that a role's skill calls one the role lacks."""

import re
from pathlib import Path

import pytest

AGENT_KIT = Path(__file__).parents[2] / "agent-kit"
SKILL_LINKS = sorted(AGENT_KIT.glob("roles/*/skills/*"))


@pytest.mark.parametrize("link", SKILL_LINKS, ids=lambda path: f"{path.parts[-3]}/{path.name}")
def test_each_link_is_a_relative_link_to_one_of_the_kits_skills(link: Path) -> None:
    target = link.readlink() if link.is_symlink() else None
    assert target == Path("../../../skills") / link.name, f"{link} must link to ../../../skills/{link.name}"
    assert (link / "SKILL.md").is_file(), f"{link} points at no skill"


@pytest.mark.parametrize("skills_dir", sorted(AGENT_KIT.glob("roles/*/skills")), ids=lambda path: path.parent.name)
def test_every_skill_a_roles_skills_call_is_one_the_role_has(skills_dir: Path) -> None:
    role_skills = {link.name for link in skills_dir.iterdir()}
    missing = {
        (name, called)
        for name in role_skills
        for path in (skills_dir / name).rglob("*.md")
        for called in re.findall(r'call the Skill tool with "([^"]+)"', path.read_text())
        if called not in role_skills
    }
    assert sorted(missing) == []
