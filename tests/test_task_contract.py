"""A task's names reach everywhere they are needed from Task in src/foundry/task.py: into the
sandbox as the AGENT_* variables the session sets, which the agent kit reads, and into the
rulesets in config/repo-policy/rulesets.yaml, which must spell them out for GitHub."""

import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from foundry import session, yaml_io
from foundry.config import Project, Role
from foundry.task import NOTES_BRANCH, Task

REPO_ROOT = Path(__file__).parents[1]
AGENT_KIT = REPO_ROOT / "agent-kit"
RULESETS = REPO_ROOT / "config" / "repo-policy" / "rulesets.yaml"


def agent_kit_files() -> list[Path]:
    """Every text file in the agent kit: its scripts, and the instructions the agent reads."""
    files = []
    for path in sorted(AGENT_KIT.rglob("*")):
        if path.is_file():
            try:
                path.read_text()
            except UnicodeDecodeError:
                continue
            files.append(path)
    return files


def test_every_variable_the_agent_kit_uses_is_one_the_sandbox_definition_sets(tmp_path: Path) -> None:
    opened = session.open_or_create(
        tmp_path, project=Project(name="p", url="git@github.com:o/p.git"), role=Role(name="dev"), task=Task("t1")
    )
    used = {
        (name, str(path.relative_to(REPO_ROOT)))
        for path in agent_kit_files()
        for name in re.findall(r"\bAGENT_[A-Z_]+\b", path.read_text())
    }

    assert [(name, where) for name, where in sorted(used) if name not in opened.definition.variables] == []


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
