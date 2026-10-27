import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from foundry import session
from foundry.config import Project, Role
from foundry.runtime_build import build_runtime
from foundry.session import SessionVariables
from foundry.task import NOTES_BRANCH, Task


def pytest_configure(config: pytest.Config) -> None:
    """Stop a run started as root before anything is collected. Only the docker tier's containers use root,
    inside them."""
    if os.geteuid() == 0:
        raise pytest.UsageError(
            "the tests run as an ordinary user, never as root: "
            "root can write anything, so the write checks would mean nothing"
        )


@pytest.fixture
def session_variables(tmp_path: Path) -> Callable[[Task], SessionVariables]:
    """The session variables a new sandbox for a task gets, from a real session under tmp_path/foundry.

    For a stand-in project and role: tests that need the variables, not a particular project.
    """

    def variables(task: Task) -> SessionVariables:
        opened = session.open_or_create(
            tmp_path / "foundry",
            project=Project(name="p", url="git@github.com:o/p.git"),
            role=Role(name="dev", ssh_key_path=tmp_path / "secrets" / "ssh" / "dev", github_token_path=None),
            task=task,
        )
        return opened.variables

    return variables


AGENT_KIT_SOURCE = Path(__file__).parents[1] / "agent-kit"


@pytest.fixture(scope="session")
def built_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of this repository's agent kit with the runtime built into it, made once per test run.

    Tests that run the kit as delivered use it, so none of them writes into the repository's agent-kit/.build/.
    Read-only by agreement: a test that changes the kit makes its own copy.
    """
    kit = tmp_path_factory.mktemp("built") / "agent-kit"
    shutil.copytree(AGENT_KIT_SOURCE, kit, symlinks=True, ignore=shutil.ignore_patterns(".build"))
    build_runtime(kit)
    return kit


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
