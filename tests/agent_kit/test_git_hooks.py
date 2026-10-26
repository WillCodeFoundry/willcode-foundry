"""agent-kit/hooks and the Stop hook, against a real repository with a local origin.

The checkouts are made by session-setup, as in a sandbox: a code checkout on the
task's branch, a notes worktree on agent-notes, and core.hooksPath pointing at the
kit, with the variables a sandbox for the task gets.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from foundry.task import NOTES_BRANCH, STATE_FILE, Task

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
TASK = Task("T1")
OTHER_TASK = Task("T2")


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


@pytest.fixture
def repo(sandbox_checkouts):
    """(code checkout, notes checkout), made by session-setup, both clean and pushed."""
    return sandbox_checkouts(TASK)


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


def task_state(name: str) -> str:
    return json.dumps(
        {"lifecycle": "feature", "state": name, "previous": None, "counts": {}, "handoff": {"commit": "", "note": ""}}
    )


def run_task(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(AGENT_KIT_PATH / "bin" / "task"), *args], env=os.environ, capture_output=True, text=True, check=False
    )


def test_code_is_pushed_only_on_the_roles_turn(sandbox_checkouts, push_task_state) -> None:
    code, _ = sandbox_checkouts(TASK, notes={STATE_FILE: task_state("ready")})
    change(code, "hello.sh")
    commit(code, "feat: hello")
    assert git(code, "push", "-q", "origin", TASK.branch, check=False).returncode == 0
    assert run_task("submit", "Ready for review.").returncode == 0

    change(code, "more.sh")
    commit(code, "feat: more")
    refused = git(code, "push", "origin", TASK.branch, check=False)
    assert refused.returncode != 0
    assert "reviewer's turn" in refused.stderr and "push no more code" in refused.stderr

    push_task_state(TASK, task_state("changes"))  # given back, without this sandbox pulling its notes
    assert git(code, "push", "-q", "origin", TASK.branch, check=False).returncode == 0


def test_no_code_is_pushed_while_the_task_state_cant_be_read(sandbox_checkouts, push_task_state) -> None:
    code, _ = sandbox_checkouts(TASK, notes={STATE_FILE: task_state("ready")})
    push_task_state(TASK, "{not json")
    change(code, "hello.sh")
    commit(code, "feat: hello")

    refused = git(code, "push", "origin", TASK.branch, check=False)

    assert refused.returncode != 0
    assert "couldn't read the task state" in refused.stderr and "can't be told" in refused.stderr


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
    return subprocess.run(
        [str(AGENT_KIT_PATH / "claude" / "hooks" / "session-check")],
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


def test_stop_is_blocked_while_the_task_state_was_changed_by_hand(sandbox_checkouts) -> None:
    _, notes = sandbox_checkouts(TASK, notes={STATE_FILE: task_state("ready")})
    (notes / TASK.state_file).write_text(task_state("approved"))
    git(notes, "commit", "-qam", f"{TASK.id}: approved")
    git(notes, "push", "-q", "origin", NOTES_BRANCH)

    decision = json.loads(stop().stdout)

    assert decision["decision"] == "block"
    assert "changed other than by $AGENT_KIT_DIR/bin/task" in decision["reason"]


def test_stop_is_blocked_while_the_task_state_cant_be_read(sandbox_checkouts, tmp_path) -> None:
    sandbox_checkouts(TASK, notes={STATE_FILE: task_state("ready")})
    (tmp_path / "origin.git").rename(tmp_path / "unreachable.git")

    decision = json.loads(stop().stdout)

    assert decision["decision"] == "block"
    assert "couldn't read the task state" in decision["reason"] and "Only the human can fix this" in decision["reason"]
    assert decision["reason"].endswith("your next stop is let through.")


def test_stop_is_blocked_while_the_task_state_on_origin_is_malformed(sandbox_checkouts, push_task_state) -> None:
    _, notes = sandbox_checkouts(TASK, notes={STATE_FILE: task_state("ready")})
    push_task_state(TASK, "{not json")
    git(notes, "pull", "-q", "--rebase", "origin", NOTES_BRANCH)

    decision = json.loads(stop().stdout)

    assert decision["decision"] == "block"
    assert "is not valid JSON" in decision["reason"] and "Only the human can fix this" in decision["reason"]


def test_block_pushes_the_roles_commits_so_the_session_can_end(sandbox_checkouts) -> None:
    code, _ = sandbox_checkouts(TASK, notes={STATE_FILE: task_state("ready")})
    change(code, "half-done.sh")
    commit(code, "feat: start the import")

    assert run_task("block", "Is CSV in scope?").returncode == 0

    head = git(code, "rev-parse", "HEAD").stdout.strip()
    assert git(code, "ls-remote", "origin", TASK.branch).stdout.split()[0] == head
    assert stop().stdout.strip() == ""


def test_stop_is_allowed_after_bin_task_and_the_humans_move(sandbox_checkouts, push_task_state) -> None:
    _, notes = sandbox_checkouts(TASK, notes={STATE_FILE: task_state("ready")})
    assert run_task("block", "Is CSV in scope?").returncode == 0
    push_task_state(TASK, task_state("ready"))
    git(notes, "pull", "-q", "--rebase", "origin", NOTES_BRANCH)

    assert stop().stdout.strip() == ""


# --- every script -------------------------------------------------------------


@pytest.mark.parametrize(
    "script",
    [
        "hooks/pre-commit",
        "hooks/pre-push",
        "hooks/prepare-commit-msg",
        "claude/hooks/session-check",
        "bin/session-init",
        "bin/session-setup",
    ],
)
def test_a_script_run_outside_a_sandbox_names_the_variable_it_lacks(script: str) -> None:
    result = subprocess.run(
        [str(AGENT_KIT_PATH / script)],
        env={"PATH": os.environ["PATH"]},
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "AGENT_" in result.stderr and "parameter null or not set" in result.stderr
