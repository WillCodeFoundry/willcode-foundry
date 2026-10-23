"""config/task-template/PROGRESS.md has the sections agent-kit/AGENTS.md says every PROGRESS.md has."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]


def headings(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("#")]


def test_the_progress_template_has_the_sections_agents_md_requires() -> None:
    agents_md = (REPO_ROOT / "agent-kit" / "AGENTS.md").read_text()
    match = re.search(r"`PROGRESS.md` always has these sections:\n\n```markdown\n(.*?)```", agents_md, re.DOTALL)
    assert match, "AGENTS.md no longer describes PROGRESS.md's sections where this test looks"

    template = (REPO_ROOT / "config" / "task-template" / "PROGRESS.md").read_text()
    assert headings(template) == headings(match[1])
