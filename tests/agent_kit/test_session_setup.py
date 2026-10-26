"""agent-kit/bin/session-setup, the agent user's part of session-init, against a local origin.

It never needs root, so it runs here as in a sandbox, with a sandbox's variables and a throwaway HOME.
"""

import json
import os
import shutil
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


def session_setup(kit_env: dict[str, str], origin: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **kit_env, "AGENT_REPO_URL": f"file://{origin}"}
    return subprocess.run(
        [str(AGENT_KIT_PATH / "bin" / "session-setup")], env=env, capture_output=True, text=True, check=False
    )


def test_a_task_without_its_branches_is_explained(kit_env, origin) -> None:
    result = session_setup(kit_env(TASK), origin)
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

    result = session_setup(kit_env(TASK), origin)
    assert result.returncode == 1
    assert f"{NOTES_BRANCH} has no {TASK.task_file}" in result.stderr
    assert not (tmp_path / "home" / ".claude").exists()  # stopped before writing instructions


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


def git_out(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def test_a_created_task_gets_both_checkouts_with_the_kits_hooks(kit_env, created_task) -> None:
    env = kit_env(TASK)

    result = session_setup(env, created_task)

    assert result.returncode == 0, result.stderr
    code, notes = Path(env["AGENT_PROJECT_DIR"]), Path(env["AGENT_NOTES_DIR"])
    assert git_out(code, "branch", "--show-current") == TASK.branch
    assert git_out(notes, "branch", "--show-current") == NOTES_BRANCH
    assert (notes / TASK.task_file).read_text() == "# Task\n"
    assert git_out(code, "config", "core.hooksPath") == str(AGENT_KIT_PATH / "hooks")


def test_the_git_identity_is_the_roles(tmp_path, kit_env, created_task) -> None:
    assert session_setup(kit_env(TASK), created_task).returncode == 0

    assert git_out(tmp_path, "config", "--global", "include.path") == str(
        AGENT_KIT_PATH / "roles" / "dev" / "gitconfig"
    )
    assert git_out(tmp_path, "config", "--global", "gpg.ssh.allowedSignersFile") == str(
        AGENT_KIT_PATH / "git" / "allowed_signers"
    )
    assert git_out(tmp_path, "config", "user.name") == "wc-foundry-dev"


def test_the_agent_starts_briefed_with_its_roles_skills(tmp_path, kit_env, created_task) -> None:
    env = kit_env(TASK)

    assert session_setup(env, created_task).returncode == 0

    claude_dir = tmp_path / "home" / ".claude"
    imports = [line for line in (claude_dir / "CLAUDE.md").read_text().splitlines() if line.startswith("@")]
    assert imports == [
        f"@{AGENT_KIT_PATH / 'AGENTS.md'}",
        f"@{AGENT_KIT_PATH / 'roles' / 'dev' / 'ROLE.md'}",
        f"@{Path(env['AGENT_NOTES_DIR']) / TASK.task_file}",
    ]
    assert (claude_dir / "skills").readlink() == AGENT_KIT_PATH / "roles" / "dev" / "skills"


def test_a_second_run_succeeds_and_changes_nothing(tmp_path, kit_env, created_task) -> None:
    env = kit_env(TASK)
    assert session_setup(env, created_task).returncode == 0
    code = Path(env["AGENT_PROJECT_DIR"])
    before = (git_out(code, "rev-parse", "HEAD"), (tmp_path / "home" / ".claude" / "CLAUDE.md").read_text())

    result = session_setup(env, created_task)

    assert result.returncode == 0, result.stderr
    assert (git_out(code, "rev-parse", "HEAD"), (tmp_path / "home" / ".claude" / "CLAUDE.md").read_text()) == before
    assert git_out(code, "branch", "--show-current") == TASK.branch


def test_a_role_that_signs_without_a_key_is_refused(tmp_path, kit_env, created_task) -> None:
    kit = tmp_path / "agent-kit"
    shutil.copytree(AGENT_KIT_PATH, kit, symlinks=True)
    gitconfig = kit / "roles" / "dev" / "gitconfig"
    gitconfig.write_text("".join(line for line in gitconfig.read_text().splitlines(True) if "signingkey" not in line))

    result = session_setup({**kit_env(TASK), "AGENT_KIT_DIR": str(kit)}, created_task)

    assert result.returncode == 1
    assert "dev signs commits but" in result.stderr and "sets no user.signingkey" in result.stderr


def test_a_skills_folder_in_place_of_the_link_is_refused(tmp_path, kit_env, created_task) -> None:
    (tmp_path / "home" / ".claude" / "skills").mkdir(parents=True)

    result = session_setup(kit_env(TASK), created_task)

    assert result.returncode == 1
    assert "is a folder, not the link to the role's skills" in result.stderr


# --- the task state -------------------------------------------------------------


def push_state(tmp_path: Path, name: str, *, note: str = "") -> str:
    """Put the task in state ``name`` on origin's notes branch, as bin/task would; returns the file's text."""
    seed = tmp_path / "seed"
    text = json.dumps(
        {"lifecycle": "feature", "state": name, "previous": None, "counts": {}, "handoff": {"commit": "", "note": note}}
    )
    (seed / TASK.state_file).write_text(text)
    git(seed, "add", TASK.state_file)
    # Signing off: an earlier session-setup made the role's gitconfig, which signs, global under this HOME.
    git(seed, "-c", "commit.gpgsign=false", "commit", "-qm", f"{TASK.id}: {name}")
    git(seed, "push", "-q", "origin", NOTES_BRANCH)
    return text


def launch_record(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".claude" / "launch.json"


def test_a_role_whose_turn_it_isnt_is_not_started(tmp_path, kit_env, created_task) -> None:
    push_state(tmp_path, "review", note="R1 fixed.")

    result = session_setup(kit_env(TASK), created_task)

    assert result.returncode == 1
    assert "reviewer's turn" in result.stderr and "R1 fixed." in result.stderr
    assert not (tmp_path / "home" / ".claude" / "CLAUDE.md").exists()


def test_the_launch_is_recorded_as_origins_notes_commit(tmp_path, kit_env, created_task) -> None:
    push_state(tmp_path, "ready")

    result = session_setup(kit_env(TASK), created_task)

    assert result.returncode == 0, result.stderr
    notes_head = git_out(tmp_path / "seed", "rev-parse", "HEAD")
    assert json.loads(launch_record(tmp_path).read_text()) == {"notes_base": notes_head}


def test_a_relaunch_sees_the_latest_task_state(tmp_path, kit_env, created_task) -> None:
    push_state(tmp_path, "ready")
    assert session_setup(kit_env(TASK), created_task).returncode == 0
    push_state(tmp_path, "review")  # handed on since: by this sandbox, or by another role's

    result = session_setup(kit_env(TASK), created_task)

    assert result.returncode == 1 and "reviewer's turn" in result.stderr


def test_a_notes_checkout_behind_and_ahead_of_origin_only_warns(tmp_path, kit_env, created_task) -> None:
    push_state(tmp_path, "ready")
    env = kit_env(TASK)
    assert session_setup(env, created_task).returncode == 0
    notes = Path(env["AGENT_NOTES_DIR"])
    (notes / TASK.notes_dir / "PROGRESS.md").write_text("local, unpushed\n")
    git(notes, "add", TASK.notes_dir)
    subprocess.run(  # with the sandbox's variables: the kit's git hooks read them
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "local"],
        cwd=notes,
        env={**os.environ, **env},
        check=True,
        capture_output=True,
    )
    push_state(tmp_path, "ready", note="pushed meanwhile")

    result = session_setup(env, created_task)

    assert result.returncode == 0, result.stderr
    assert "isn't up to date" in result.stderr and "git pull --rebase" in result.stderr


def test_a_task_without_a_state_is_started_with_a_warning(tmp_path, kit_env, created_task) -> None:
    launch_record(tmp_path).parent.mkdir(parents=True)
    launch_record(tmp_path).write_text("left by an earlier launch\n")

    result = session_setup(kit_env(TASK), created_task)

    assert result.returncode == 0, result.stderr
    assert f"has no {Path(TASK.state_file).name}" in result.stderr and "no turns" in result.stderr
    assert not launch_record(tmp_path).exists()


def test_a_task_state_that_cant_be_read_stops_the_launch(tmp_path, kit_env, created_task) -> None:
    push_state(tmp_path, "nowhere")

    result = session_setup(kit_env(TASK), created_task)

    assert result.returncode == 1
    assert "couldn't read the task state" in result.stderr and "not starting dev" in result.stderr
    assert not launch_record(tmp_path).exists()
