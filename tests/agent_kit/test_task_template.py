"""config/task-template/ starts the notes agent-kit/AGENTS.md describes, and its LOG.md example passes pre-commit."""

import re
from pathlib import Path

from agent_runtime import git_hooks

REPO_ROOT = Path(__file__).parents[2]


def test_the_template_starts_the_log() -> None:
    assert (REPO_ROOT / "config" / "task-template" / git_hooks.LOG_FILE).is_file()


def test_the_log_example_in_agents_md_has_the_headings_pre_commit_accepts() -> None:
    agents_md = (REPO_ROOT / "agent-kit" / "AGENTS.md").read_text()
    match = re.search(r"### `LOG.md`\n.*?```markdown\n(.*?)```", agents_md, re.DOTALL)
    assert match, "AGENTS.md no longer shows a LOG.md entry where this test looks"

    headings = [line for line in match[1].splitlines() if line.startswith("## ")]
    assert headings
    assert all(git_hooks.LOG_HEADING.fullmatch(line) for line in headings), headings
