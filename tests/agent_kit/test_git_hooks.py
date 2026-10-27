"""agent-kit/hooks and the Stop hook, against a real repository with a local origin.

The checkouts are made by session-setup, as in a sandbox: a code checkout on the
task's branch, a notes worktree on agent-notes, and core.hooksPath pointing at the
kit, with the variables a sandbox for the task gets.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from foundry.task import NOTES_BRANCH, Task
from tests.agent_kit.conftest import runtime_command
from tests.conftest import TASK, git

SETTINGS = json.loads((Path(__file__).parents[2] / "agent-kit" / "claude" / "managed-settings.json").read_text())
(STOP_COMMAND,) = (hook["command"] for entry in SETTINGS["hooks"]["Stop"] for hook in entry["hooks"])
OTHER_TASK = Task("T2")


@pytest.fixture
def repo(monkeypatch, kit_env, created_task):
    """(code checkout, notes checkout), made by session-setup from a created task's origin, both clean and
    pushed."""
    # session-setup includes the role's gitconfig, which signs with the role's key; there is no
    # private key here, so signing is turned off by git's environment override, which beats any file.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "commit.gpgsign")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")

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
    return Path(env["AGENT_PROJECT_DIR"]), Path(env["AGENT_NOTES_DIR"])


def commit(cwd: Path, *message: str) -> subprocess.CompletedProcess[str]:
    args = [arg for part in message for arg in ("-m", part)]
    return git(cwd, "commit", "-q", *args, check=False)


def change(cwd: Path, name: str) -> None:
    path = cwd / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{name}\n")
    git(cwd, "add", name)


# --- code checkout -----------------------------------------------------------


def last_message(cwd: Path) -> str:
    return git(cwd, "log", "-1", "--format=%B").stdout.rstrip("\n") + "\n"  # %B adds a blank line


def test_the_task_trailer_is_added_to_a_commit_message(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    assert commit(code, "feat: hello", "Why.").returncode == 0
    assert last_message(code) == f"feat: hello\n\nWhy.\n\nTask: {TASK.id}\n"


def test_the_trailer_is_added_to_a_message_from_a_file(repo, tmp_path) -> None:
    code, _ = repo
    change(code, "hello.sh")
    (tmp_path / "message").write_text("feat: hello\n")
    assert git(code, "commit", "-q", "-F", str(tmp_path / "message"), check=False).returncode == 0
    assert last_message(code).endswith(f"\n\nTask: {TASK.id}\n")


def test_the_trailer_is_never_added_twice(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    commit(code, "feat: hello", f"Task: {TASK.id}")
    assert last_message(code).count(f"Task: {TASK.id}") == 1
    git(code, "commit", "-q", "--amend", "--no-edit")
    assert last_message(code).count(f"Task: {TASK.id}") == 1


def test_the_trailer_is_added_even_with_no_verify(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    assert git(code, "commit", "-q", "--no-verify", "-m", "feat: hello", check=False).returncode == 0
    assert last_message(code).endswith(f"\n\nTask: {TASK.id}\n")


def test_an_empty_message_still_aborts_the_commit(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    result = git(code, "commit", "-q", "-m", "", check=False)
    assert result.returncode != 0
    assert git(code, "rev-list", "--count", "HEAD").stdout.strip() == "1"  # only the seed commit


def test_notes_on_the_task_branch_are_refused(repo) -> None:
    code, _ = repo
    change(code, f"{TASK.notes_dir}/PROGRESS.md")
    result = commit(code, "notes")
    assert result.returncode != 0 and f"Task notes belong on {NOTES_BRANCH}" in result.stderr


def test_a_note_named_file_outside_agent_is_accepted(repo) -> None:
    code, notes = repo
    (notes / TASK.notes_dir / "PROGRESS.md").write_text("# Progress\n")
    change(code, "PROGRESS.md")
    result = commit(code, "the project's own progress file")
    assert result.returncode == 0, result.stderr


def test_notes_under_a_nested_agent_folder_are_refused(repo) -> None:
    code, _ = repo
    change(code, f"src/{TASK.notes_dir}/PROGRESS.md")
    result = commit(code, "notes written from a subfolder")
    assert result.returncode != 0 and f"Task notes belong on {NOTES_BRANCH}" in result.stderr


def test_a_code_file_is_accepted(repo) -> None:
    code, _ = repo
    change(code, "NOTES.md")
    result = commit(code, "notes")
    assert result.returncode == 0, result.stderr


def test_push_of_the_task_branch_is_accepted_but_other_refs_are_refused(repo) -> None:
    code, _ = repo
    change(code, "hello.sh")
    commit(code, "feat: hello")
    assert git(code, "push", "-q", "origin", TASK.branch, check=False).returncode == 0
    for target in ("HEAD:refs/heads/other", f"HEAD:refs/heads/{OTHER_TASK.branch}", "HEAD:refs/tags/v1"):
        result = git(code, "push", "origin", target, check=False)
        assert result.returncode != 0 and "only push" in result.stderr, target


def test_a_kit_without_its_runtime_refuses_the_commit(repo, built_kit, tmp_path) -> None:
    """The hooks find the runtime beside them; missing, they fail and git stops, rather than run no rules."""
    code, _ = repo
    kit = tmp_path / "kit-without-runtime"
    shutil.copytree(built_kit, kit, symlinks=True, ignore=shutil.ignore_patterns(".build"))
    git(code, "config", "core.hooksPath", str(kit / "hooks"))
    change(code, "hello.sh")

    result = commit(code, "feat: hello")

    assert result.returncode != 0
    assert f"pre-commit: refusing: {kit / '.build' / 'agent_runtime.pyz'} is missing" in result.stderr
    assert git(code, "rev-list", "--count", "HEAD").stdout.strip() == "1"  # only the seed commit


def test_the_hooks_ignore_a_runtime_named_by_the_environment(repo, tmp_path, monkeypatch) -> None:
    """The agent sets its git commands' environment; AGENT_KIT_DIR pointing elsewhere changes nothing."""
    code, _ = repo
    monkeypatch.setenv("AGENT_KIT_DIR", str(tmp_path / "elsewhere"))
    change(code, f"{TASK.notes_dir}/PROGRESS.md")

    result = commit(code, "notes")

    assert result.returncode != 0 and f"Task notes belong on {NOTES_BRANCH}" in result.stderr


# --- notes checkout ----------------------------------------------------------


def test_notes_in_own_folder_are_accepted_without_a_task_trailer(repo) -> None:
    _, notes = repo
    change(notes, f"{TASK.notes_dir}/PROGRESS.md")
    assert commit(notes, f"{TASK.id}: progress").returncode == 0
    assert git(notes, "push", "-q", "origin", NOTES_BRANCH, check=False).returncode == 0


def test_a_changed_task_md_is_accepted(repo) -> None:
    _, notes = repo
    (notes / TASK.task_file).write_text("changed\n")
    git(notes, "add", TASK.task_file)
    result = commit(notes, f"{TASK.id}: write the task")
    assert result.returncode == 0, result.stderr


def test_another_tasks_folder_is_refused(repo) -> None:
    _, notes = repo
    change(notes, f"{OTHER_TASK.notes_dir}/PROGRESS.md")
    result = commit(notes, f"{OTHER_TASK.id}: progress")
    assert result.returncode != 0 and f"only change files in {TASK.notes_dir}/" in result.stderr


# --- Stop hook ---------------------------------------------------------------


def stop(active: bool = False, *, raw_input: str | None = None) -> subprocess.CompletedProcess[str]:
    """The Stop hook, run as Claude Code runs it: its command from managed settings, through a shell."""
    return subprocess.run(
        STOP_COMMAND,
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


def test_stop_is_allowed_when_the_hook_is_already_looping(repo) -> None:
    code, _ = repo
    (code / "wip.txt").write_text("x\n")
    assert stop(active=True).stdout.strip() == ""


@pytest.mark.parametrize("raw_input", ['{"stop_hook_active" : true}', '{\n  "stop_hook_active":\ttrue\n}'])
def test_the_looping_flag_is_read_whatever_the_json_spacing(repo, raw_input: str) -> None:
    code, _ = repo
    (code / "wip.txt").write_text("x\n")
    assert stop(raw_input=raw_input).stdout.strip() == ""


@pytest.mark.parametrize("raw_input", ["not json", "[]", '{"stop_hook_active": "true"}'])
def test_input_that_is_not_the_looping_flag_still_gets_checked(repo, raw_input: str) -> None:
    code, _ = repo
    (code / "wip.txt").write_text("x\n")
    assert json.loads(stop(raw_input=raw_input).stdout)["decision"] == "block"


# --- every script -------------------------------------------------------------

RUNTIME = ("<python>", "-I", "<kit>/.build/agent_runtime.pyz")


@pytest.mark.parametrize(
    "command",
    [
        ("<kit>/hooks/pre-commit",),
        ("<kit>/hooks/pre-push",),
        ("<kit>/hooks/prepare-commit-msg", "<kit>/message"),
        (*RUNTIME, "hook", "session-check"),
        (*RUNTIME, "session-init"),
        (*RUNTIME, "session-setup"),
    ],
)
def test_a_command_run_outside_a_sandbox_names_the_variable_it_lacks(built_kit, command: tuple[str, ...]) -> None:
    argv = [arg.replace("<kit>", str(built_kit)).replace("<python>", sys.executable) for arg in command]
    result = subprocess.run(
        argv, env={"PATH": os.environ["PATH"]}, input="", capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert "AGENT_" in result.stderr and "not set" in result.stderr
