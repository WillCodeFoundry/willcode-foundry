import dataclasses
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from foundry import paths
from foundry.session import SessionVariables
from foundry.task import NOTES_BRANCH, Task


@pytest.fixture
def kit_env(
    tmp_path: Path, built_kit: Path, session_variables: Callable[[Task], SessionVariables]
) -> Callable[[Task], dict[str, str]]:
    """The variables a sandbox for a task gets, so the kit is tested with exactly the names foundry sets.

    Pointed at the agent kit as delivered, with its runtime built (``built_kit``), and at checkouts
    under tmp_path/work (the notes checkout beside the code one, at tmp_path/work/p-notes); a test
    replaces any other variable it needs, e.g. AGENT_REPO_URL for a local origin.
    """

    def env(task: Task) -> dict[str, str]:
        variables = dataclasses.replace(
            session_variables(task), agent_kit_dir=built_kit, project_dir=str(tmp_path / "work" / "p")
        )
        return variables.to_env()

    return env


def runtime_command(kit_dir: Path, *args: str) -> list[str]:
    """A call into the runtime built into ``kit_dir``, as contract.command makes it, but on this interpreter.

    The tests that run a command exactly as written (managed settings, the git hooks' stubs) use the
    template's interpreter, /usr/bin/python3, as the sandbox does.
    """
    return [sys.executable, "-I", str(paths.runtime_pyz(kit_dir)), *args]


# --- a project's origin, for setting a sandbox up against ----------------------------------

TASK = Task("T1")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository with only main: no task branch, no agent-notes."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key, value in {"user.name": "t", "user.email": "t@t", "commit.gpgsign": "false"}.items():
        git(tmp_path, "config", "--global", key, value)
    bare = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-q", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(bare), str(seed))
    (seed / "README.md").write_text("hi\n")
    git(seed, "add", ".")
    git(seed, "commit", "-qm", "init")
    git(seed, "push", "-q", "origin", "HEAD:main")
    return bare


@pytest.fixture
def created_task(tmp_path: Path, origin: Path) -> Path:
    """The origin once `foundry task create` has run: the task's branch, and its TASK.md on the notes branch."""
    seed = tmp_path / "seed"
    git(seed, "push", "-q", "origin", f"HEAD:refs/heads/{TASK.branch}")
    git(seed, "switch", "-q", "--orphan", NOTES_BRANCH)
    (seed / TASK.notes_dir).mkdir(parents=True)
    (seed / TASK.task_file).write_text("# Task\n")
    git(seed, "add", TASK.notes_dir)
    git(seed, "commit", "-qm", f"Add task {TASK.id}")
    git(seed, "push", "-q", "origin", NOTES_BRANCH)
    return origin
