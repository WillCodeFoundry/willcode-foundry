import dataclasses
import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from foundry.session import SessionVariables
from foundry.task import NOTES_BRANCH, Task

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"


@pytest.fixture
def kit_env(tmp_path: Path, session_variables: Callable[[Task], SessionVariables]) -> Callable[[Task], dict[str, str]]:
    """The variables a sandbox for a task gets, so the kit is tested with exactly the names foundry sets.

    Pointed at this repository's agent kit and at checkouts under tmp_path/work (the notes
    checkout beside the code one, at tmp_path/work/p-notes); a test replaces any other variable
    it needs, e.g. AGENT_REPO_URL for a local origin.
    """

    def env(task: Task) -> dict[str, str]:
        variables = dataclasses.replace(
            session_variables(task), agent_kit_dir=AGENT_KIT_PATH, project_dir=str(tmp_path / "work" / "p")
        )
        return variables.to_env()

    return env


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def sandbox_checkouts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kit_env: Callable[[Task], dict[str, str]]
) -> Callable[..., tuple[Path, Path]]:
    """Make a sandbox's checkouts for a task: (code checkout, notes checkout), by session-setup, clean and pushed.

    From a local origin holding main, the task's branch, and its notes folder on the notes branch: its
    TASK.md, plus ``notes`` (file name -> text). The variables a sandbox gets are set in this process's
    environment, as git hooks and the kit's commands run inside the sandbox would see them; ``role``
    launches another role than dev, and ``kit_dir`` points them at another copy of the kit. HOME is a
    throwaway one, and git doesn't sign.
    """

    def make(
        task: Task, *, notes: Mapping[str, str] | None = None, role: str = "dev", kit_dir: Path | None = None
    ) -> tuple[Path, Path]:
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        monkeypatch.setenv("HOME", str(home))  # keep the developer's global git config out
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        for key, value in {"user.name": "t", "user.email": "t@t", "init.defaultBranch": "main"}.items():
            _git(tmp_path, "config", "--global", key, value)
        # session-setup includes the role's gitconfig, which signs with the role's key; there is no
        # private key here, so signing is turned off by git's environment override, which beats any file.
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "commit.gpgsign")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")

        origin = tmp_path / "origin.git"
        _git(tmp_path, "init", "--bare", "-q", str(origin))
        seed = tmp_path / "seed"
        _git(tmp_path, "clone", "-q", str(origin), str(seed))
        (seed / "README.md").write_text("hi\n")
        _git(seed, "add", ".")
        _git(seed, "commit", "-qm", "init")
        _git(seed, "push", "-q", "origin", "main", f"main:{task.branch}")
        _git(seed, "switch", "-q", "--orphan", NOTES_BRANCH)
        (seed / task.notes_dir).mkdir(parents=True)
        (seed / task.task_file).write_text("# Task\n")
        for name, text in (notes or {}).items():
            (seed / task.notes_dir / name).write_text(text)
        _git(seed, "add", task.notes_dir)
        _git(seed, "commit", "-qm", f"{task.id}: create task")
        _git(seed, "push", "-q", "origin", NOTES_BRANCH)

        env = {**kit_env(task), "AGENT_REPO_URL": f"file://{origin}", "AGENT_ROLE": role}
        if kit_dir is not None:
            env["AGENT_KIT_DIR"] = str(kit_dir)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        setup = subprocess.run(
            [str(Path(env["AGENT_KIT_DIR"]) / "bin" / "session-setup")],
            env=os.environ,
            capture_output=True,
            text=True,
            check=False,
        )
        assert setup.returncode == 0, setup.stderr
        return Path(env["AGENT_PROJECT_DIR"]), Path(env["AGENT_NOTES_DIR"])

    return make


@pytest.fixture
def push_task_state(tmp_path: Path) -> Callable[..., None]:
    """Push a task state to origin's notes branch from outside the sandbox: as the human, or another role.

    From sandbox_checkouts' seed repository, which tracks origin's notes branch, as ``email``.
    """

    def push(task: Task, text: str, *, email: str = "human@example.com") -> None:
        seed = tmp_path / "seed"
        unsigned = ("-c", "commit.gpgsign=false")
        _git(seed, *unsigned, "pull", "-q", "--rebase", "origin", NOTES_BRANCH)
        (seed / task.state_file).write_text(text)
        _git(seed, "add", task.state_file)
        _git(seed, *unsigned, "-c", f"user.email={email}", "commit", "-qm", f"{task.id}: moved")
        _git(seed, "push", "-q", "origin", NOTES_BRANCH)

    return push
