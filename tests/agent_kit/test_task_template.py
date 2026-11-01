"""config/task-template/ starts the LOG.md that agent-kit/AGENTS.md describes and pre-commit keeps append-only."""

from pathlib import Path

from agent_runtime import git_hooks

REPO_ROOT = Path(__file__).parents[2]


def test_the_template_starts_the_log() -> None:
    assert (REPO_ROOT / "config" / "task-template" / git_hooks.LOG_FILE).is_file()
