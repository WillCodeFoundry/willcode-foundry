"""agent-kit/bin/session-init's refusals for a task that hasn't been created, and
session-harden's refusal to run outside a sandbox.

Only paths that exit before hardening are run here: session-harden removes
sudo from the machine it runs on, so it is only run as far as its refusal.
"""

import os
import subprocess
from pathlib import Path

import pytest

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"


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


def session_init(tmp_path: Path, origin: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "AGENT_TASK": "T1",
        "AGENT_ROLE": "dev",
        "AGENT_REPO_URL": f"file://{origin}",
        "AGENT_PROJECT_DIR": str(tmp_path / "work" / "p"),
        "AGENT_NOTES_DIR": str(tmp_path / "work" / "p-notes"),
        "AGENT_KIT_DIR": str(AGENT_KIT_PATH),
    }
    return subprocess.run(
        [str(AGENT_KIT_PATH / "bin" / "session-init")], env=env, capture_output=True, text=True, check=False
    )


def test_a_task_without_its_branches_is_explained(tmp_path, origin) -> None:
    result = session_init(tmp_path, origin)
    assert result.returncode == 1
    assert "task T1 has not been created" in result.stderr
    assert "branch task/T1" in result.stderr and "branch agent-notes" in result.stderr


def test_a_task_without_its_task_md_is_explained(tmp_path, origin) -> None:
    seed = tmp_path / "seed"
    git(seed, "push", "-q", "origin", "HEAD:refs/heads/task/T1")
    git(seed, "switch", "-q", "--orphan", "agent-notes")
    (seed / "x").write_text("x\n")
    git(seed, "add", "x")
    git(seed, "commit", "-qm", "notes")
    git(seed, "push", "-q", "origin", "agent-notes")

    result = session_init(tmp_path, origin)
    assert result.returncode == 1
    assert "agent-notes has no .agent/T1/TASK.md" in result.stderr
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
