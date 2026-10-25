"""agent-kit/bin/session-init's refusals for a task that hasn't been created, and
session-harden's refusal to run outside a sandbox.

Only paths that exit before hardening are run here: session-harden removes
sudo from the machine it runs on, so it is only run as far as its refusal.
"""

import os
import subprocess
from pathlib import Path

import pytest

from foundry.task import NOTES_BRANCH, Task

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
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


def session_init(kit_env: dict[str, str], origin: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **kit_env, "AGENT_REPO_URL": f"file://{origin}"}
    return subprocess.run(
        [str(AGENT_KIT_PATH / "bin" / "session-init")], env=env, capture_output=True, text=True, check=False
    )


def test_a_task_without_its_branches_is_explained(kit_env, origin) -> None:
    result = session_init(kit_env(TASK), origin)
    assert result.returncode == 1
    assert f"task {TASK.id} has not been created" in result.stderr
    assert f"branch {TASK.branch}" in result.stderr and f"branch {NOTES_BRANCH}" in result.stderr


def test_a_task_without_its_task_md_is_explained(tmp_path, kit_env, origin) -> None:
    seed = tmp_path / "seed"
    git(seed, "push", "-q", "origin", f"HEAD:refs/heads/{TASK.branch}")
    git(seed, "switch", "-q", "--orphan", NOTES_BRANCH)
    (seed / "x").write_text("x\n")
    git(seed, "add", "x")
    git(seed, "commit", "-qm", "notes")
    git(seed, "push", "-q", "origin", NOTES_BRANCH)

    result = session_init(kit_env(TASK), origin)
    assert result.returncode == 1
    assert f"{NOTES_BRANCH} has no {TASK.task_file}" in result.stderr
    assert not (tmp_path / "home" / ".claude").exists()  # stopped before writing instructions


@pytest.mark.parametrize("sudo_user", [None, "root", "will"])
def test_session_harden_refuses_outside_a_sandbox_before_changing_anything(sudo_user: str | None) -> None:
    # Never run with SUDO_USER=agent: as root, that would harden this machine.
    env = {"PATH": os.environ["PATH"], "AGENT_KIT_DIR": str(AGENT_KIT_PATH)}
    if sudo_user is not None:
        env["SUDO_USER"] = sudo_user
    result = subprocess.run(
        [str(AGENT_KIT_PATH / "bin" / "session-harden")], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert "only runs inside a foundry sandbox" in result.stderr
