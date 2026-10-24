"""A task's names agree everywhere they are spelled out: Task in src/foundry/task.py, the agent kit's
agent-kit/lib/task.sh, and the rulesets in config/repo-policy/rulesets.yaml that protect a task's branches."""

import os
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from foundry import yaml_io
from foundry.task import NOTES_BRANCH, TASK_FILE, Task

REPO_ROOT = Path(__file__).parents[1]
TASK_SH = REPO_ROOT / "agent-kit" / "lib" / "task.sh"
RULESETS = REPO_ROOT / "config" / "repo-policy" / "rulesets.yaml"


def source_task_sh(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = (
        'source "$1"; '
        'printf "%s\\n" "$TASK_BRANCH" "$NOTES_BRANCH" "$TASK_NOTES_RELATIVE_PATH" "$TASK_FILE_RELATIVE_PATH"'
    )
    return subprocess.run(
        ["bash", "-c", script, "bash", str(TASK_SH)], env=env, capture_output=True, text=True, check=False
    )


def test_the_agent_kit_names_a_task_as_task_py_does() -> None:
    result = source_task_sh({"PATH": os.environ["PATH"], "AGENT_TASK": "t1"})

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        Task("t1").branch,
        NOTES_BRANCH,
        Task("t1").notes_dir,
        f"{Task('t1').notes_dir}/{TASK_FILE}",
    ]


def test_the_agent_kit_refuses_to_name_a_task_without_its_id() -> None:
    result = source_task_sh({"PATH": os.environ["PATH"]})
    assert result.returncode != 0 and "AGENT_TASK is not set" in result.stderr


def ref_name_lists_naming_task_branches() -> list[tuple[str, list[str]]]:
    """Each include or exclude list, by ruleset name, that names a task's branch or the notes branch.

    Found by either name, so that changing one name alone still finds the list, and fails on the other.
    """
    task_ref = f"refs/heads/{Task('t1').branch}"
    notes_ref = f"refs/heads/{NOTES_BRANCH}"
    rulesets: list[dict[str, Any]] = yaml_io.load(RULESETS)["rulesets"]
    found = []
    for ruleset in rulesets:
        ref_name = ruleset.get("conditions", {}).get("ref_name", {})
        for key in ("include", "exclude"):
            patterns: list[str] = ref_name.get(key, [])
            if notes_ref in patterns or any(fnmatch(task_ref, pattern) for pattern in patterns):
                found.append((f"{ruleset['name']} {key}", patterns))
    return found


def test_the_rulesets_name_a_tasks_branches_as_task_py_does() -> None:
    lists = ref_name_lists_naming_task_branches()

    assert lists, f"no ruleset in {RULESETS.name} names a task's branch or {NOTES_BRANCH}"
    for where, patterns in lists:
        assert any(fnmatch(f"refs/heads/{Task('t1').branch}", pattern) for pattern in patterns), where
        assert f"refs/heads/{NOTES_BRANCH}" in patterns, where
