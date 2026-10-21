"""agent-kit/hooks and the Stop hook, against a real repository with a local origin.

Mirrors what session-init sets up in a sandbox: a code checkout on task/T1,
a notes worktree on agent-notes, and core.hooksPath pointing at the kit.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

KIT = Path(__file__).parents[2] / "agent-kit"
TASK = "T1"


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """(code checkout, notes checkout), both clean and pushed."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))  # keep the developer's global git config out
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key, value in {
        "user.name": "t",
        "user.email": "t@t",
        "commit.gpgsign": "false",
        "init.defaultBranch": "main",
    }.items():
        git(tmp_path, "config", "--global", key, value)

    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-q", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(origin), str(seed))
    (seed / "README.md").write_text("hi\n")
    git(seed, "add", ".")
    git(seed, "commit", "-qm", "init")
    git(seed, "push", "-q", "origin", "main", f"main:task/{TASK}")
    git(seed, "switch", "-q", "--orphan", "agent-notes")
    (seed / ".agent" / TASK).mkdir(parents=True)
    (seed / ".agent" / TASK / "TASK.md").write_text("# Task\n")
    git(seed, "add", ".agent")
    git(seed, "commit", "-qm", f"{TASK}: create task")
    git(seed, "push", "-q", "origin", "agent-notes")

    code, notes = tmp_path / "work" / "p", tmp_path / "work" / "p-notes"
    git(tmp_path, "clone", "-q", str(origin), str(code))
    git(code, "switch", "-q", f"task/{TASK}")
    git(code, "worktree", "add", "-q", "--track", "-b", "agent-notes", str(notes), "origin/agent-notes")
    git(code, "config", "core.hooksPath", str(KIT / "hooks"))
    monkeypatch.setenv("AGENT_TASK", TASK)
    monkeypatch.setenv("AGENT_PROJECT_DIR", str(code))
    monkeypatch.setenv("AGENT_NOTES_DIR", str(notes))
    return code, notes


def commit(cwd: Path, *message: str) -> subprocess.CompletedProcess[str]:
    args = [arg for part in message for arg in ("-m", part)]
    return git(cwd, "commit", "-q", *args, check=False)


def change(cwd: Path, name: str) -> None:
    path = cwd / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{name}\n")
    git(cwd, "add", name)


# --- code checkout -----------------------------------------------------------


def test_code_commit_with_task_trailer_is_accepted(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    assert commit(code, "feat: hello", "Task: T1").returncode == 0


def test_code_commit_without_task_trailer_is_refused(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    result = commit(code, "feat: hello")
    assert result.returncode != 0 and "Task: T1" in result.stderr


def test_co_authored_by_is_refused(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    result = commit(code, "feat: hello", "Task: T1\nCo-Authored-By: Claude <noreply@anthropic.com>")
    assert result.returncode != 0 and "Co-Authored-By" in result.stderr


def test_attribution_line_is_refused(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    result = commit(code, "feat: hello", "Generated with Claude Code", "Task: T1")
    assert result.returncode != 0 and "attribution" in result.stderr


def test_notes_on_the_task_branch_are_refused(repo) -> None:
    code, _ = repo
    change(code, ".agent/T1/PROGRESS.md")
    result = commit(code, "notes", "Task: T1")
    assert result.returncode != 0 and "do not belong" in result.stderr


def test_credential_files_are_refused(repo) -> None:
    code, _ = repo
    change(code, "id_ed25519")
    result = commit(code, "oops", "Task: T1")
    assert result.returncode != 0 and "credential" in result.stderr


def test_push_of_the_task_branch_is_accepted_but_other_branches_are_refused(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    commit(code, "feat: hello", "Task: T1")
    assert git(code, "push", "-q", "origin", f"task/{TASK}", check=False).returncode == 0
    result = git(code, "push", "origin", "HEAD:refs/heads/other", check=False)
    assert result.returncode != 0 and "only push" in result.stderr


def test_force_push_and_delete_are_refused(repo) -> None:
    code, _ = repo
    git(code, "commit", "-q", "--allow-empty", "-m", "x", "-m", "Task: T1")
    git(code, "push", "-q", "origin", f"task/{TASK}")
    git(code, "reset", "-q", "--hard", "HEAD~1")
    git(code, "commit", "-q", "--allow-empty", "-m", "diverge", "-m", "Task: T1")
    result = git(code, "push", "--force", "origin", f"task/{TASK}", check=False)
    assert result.returncode != 0 and "rewrite history" in result.stderr
    result = git(code, "push", "origin", f":task/{TASK}", check=False)
    assert result.returncode != 0 and "Deleting" in result.stderr


# --- notes checkout ----------------------------------------------------------


def test_notes_in_own_folder_are_accepted_without_a_task_trailer(repo) -> None:
    _, notes = repo
    change(notes, ".agent/T1/PROGRESS.md")
    assert commit(notes, "T1: progress").returncode == 0
    assert git(notes, "push", "-q", "origin", "agent-notes", check=False).returncode == 0


def test_task_md_is_refused(repo) -> None:
    _, notes = repo
    (notes / ".agent" / "T1" / "TASK.md").write_text("changed\n")
    git(notes, "add", ".agent/T1/TASK.md")
    result = commit(notes, "T1: edit")
    assert result.returncode != 0 and "owned by the human" in result.stderr


def test_another_tasks_folder_is_refused(repo) -> None:
    _, notes = repo
    change(notes, ".agent/T2/PROGRESS.md")
    result = commit(notes, "T2: progress")
    assert result.returncode != 0 and "only change files inside" in result.stderr


def test_co_authored_by_is_refused_on_the_notes_branch_too(repo) -> None:
    _, notes = repo
    change(notes, ".agent/T1/PROGRESS.md")
    result = commit(notes, "T1: progress", "Co-Authored-By: x <x@x>")
    assert result.returncode != 0 and "Co-Authored-By" in result.stderr


# --- Stop hook ---------------------------------------------------------------


def stop(active: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(KIT / "claude" / "hooks" / "session-check")],
        input=json.dumps({"stop_hook_active": active}),
        capture_output=True,
        text=True,
        env=os.environ,
    )


def test_stop_is_allowed_when_both_checkouts_are_clean_and_pushed(repo) -> None:
    result = stop()
    assert result.returncode == 0 and result.stdout.strip() == ""


def test_stop_is_blocked_with_uncommitted_or_unpushed_work(repo) -> None:
    code, notes = repo
    (code / "wip.txt").write_text("x\n")
    change(notes, ".agent/T1/PROGRESS.md")
    commit(notes, "T1: progress")
    decision = json.loads(stop().stdout)
    assert decision["decision"] == "block"
    assert "code checkout has uncommitted changes" in decision["reason"]
    assert "notes checkout has commits not pushed" in decision["reason"]


def test_stop_is_allowed_when_the_hook_is_already_looping(repo) -> None:
    code, _ = repo
    (code / "wip.txt").write_text("x\n")
    assert stop(active=True).stdout.strip() == ""
