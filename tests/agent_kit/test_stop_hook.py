"""The Stop hook as delivered: the managed settings' command, run against checkouts with work in them. Its
rules are tested in-process, in tests/agent_runtime/test_claude_hooks.py.

The checkouts are made by session-setup, as in a sandbox: a code checkout on the task's branch and a notes
worktree on agent-notes, with the variables a sandbox for the task gets. The git hooks are left out: they run
the runtime through the link root mode makes, which a host doesn't have; tests/sandbox_image/test_git_hooks.py
runs them.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import TASK, UNSIGNED, git
from tests.support.kit import HOOK_COMMANDS, hook_command, runtime_command

(STOP_COMMAND,) = HOOK_COMMANDS["Stop"]


@pytest.fixture
def repo(monkeypatch, kit_env, created_task, tmp_path):
    """(code checkout, notes checkout), made by session-setup from a created task's origin, both clean and
    pushed."""
    # session-setup includes the role's gitconfig, which signs with the role's key; there is no
    # private key here, so signing is turned off by git's environment override, which beats any file.
    for name, value in UNSIGNED.items():
        monkeypatch.setenv(name, value)

    env = {**kit_env(TASK), "AGENT_REPO_URL": f"file://{created_task}"}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    setup = subprocess.run(
        runtime_command(Path(env["AGENT_KIT_DIR"]), "session-setup"),
        env=os.environ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert setup.returncode == 0, setup.stderr
    code, notes = Path(env["AGENT_PROJECT_DIR"]), Path(env["AGENT_NOTES_DIR"])
    no_hooks = tmp_path / "no-hooks"
    no_hooks.mkdir()
    git(code, "config", "core.hooksPath", str(no_hooks))  # the notes worktree shares the repository's config
    return code, notes


def commit(cwd: Path, *message: str) -> subprocess.CompletedProcess[str]:
    args = [arg for part in message for arg in ("-m", part)]
    return git(cwd, "commit", "-q", *args, check=False)


def change(cwd: Path, name: str) -> None:
    path = cwd / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{name}\n")
    git(cwd, "add", name)


# --- Stop hook ---------------------------------------------------------------


def stop(active: bool = False, *, raw_input: str | None = None) -> subprocess.CompletedProcess[str]:
    """The Stop hook, run as Claude Code runs it: its command from managed settings, through a shell."""
    return subprocess.run(
        hook_command(STOP_COMMAND, Path(os.environ["AGENT_KIT_DIR"])),
        shell=True,
        input=json.dumps({"stop_hook_active": active}) if raw_input is None else raw_input,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ,
    )


def test_stop_is_allowed_when_both_checkouts_are_clean_and_pushed(repo) -> None:
    result = stop()
    assert result.returncode == 0 and result.stdout.strip() == ""


def test_stop_is_blocked_with_uncommitted_or_unpushed_work(repo) -> None:
    code, notes = repo
    (code / "wip.txt").write_text("x\n")
    change(notes, f"{TASK.notes_dir}/PROGRESS.md")
    commit(notes, f"{TASK.id}: progress")
    decision = json.loads(stop().stdout)
    assert decision["decision"] == "block"
    assert "code checkout has uncommitted changes; notes checkout" in decision["reason"]
    assert "notes checkout has commits not pushed" in decision["reason"]
    assert decision["reason"].endswith('Commit and push that work (see "Git rules" in AGENTS.md), then finish.')
