"""Unsaved work, in-process, against real checkouts that session_setup made: as check-unsaved-work reports it after an
agent run, and as session-check blocks a stop on it. Both share agent_runtime.unsaved_work.describe_unsaved_work.

tests/agent_kit/test_stop_hook.py runs both once as the kit delivers them.
"""

import io
import json
import shutil
from pathlib import Path

import pytest

from agent_runtime import contract
from agent_runtime.commands import check_unsaved_work, claude_hook
from agent_runtime.unsaved_work import describe_unsaved_work
from tests.support import TASK, ProcessEnvironment, git

Checkouts = tuple[contract.SessionVariables, Path, Path]


def checkout_status(variables: contract.SessionVariables, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """check-unsaved-work's (exit code, stdout)."""
    exit_code = check_unsaved_work.report(describe_unsaved_work(variables))
    return exit_code, capsys.readouterr().out


def stop(variables: contract.SessionVariables, raw_input: str = '{"stop_hook_active": false}') -> str:
    """session-check's decision on this stop, as the JSON it prints; empty when the stop goes through."""
    stdout = io.StringIO()
    assert claude_hook.session_check(io.StringIO(raw_input), stdout, variables) == 0
    return stdout.getvalue()


def block_reason(variables: contract.SessionVariables, raw_input: str = '{"stop_hook_active": false}') -> str:
    decision = json.loads(stop(variables, raw_input))
    assert decision["decision"] == "block"
    return str(decision["reason"])


def commit(cwd: Path, name: str, message: str) -> None:
    (cwd / name).parent.mkdir(parents=True, exist_ok=True)
    (cwd / name).write_text(f"{name}\n")
    git(cwd, "add", name)
    git(cwd, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", message)


def code_line(variables: contract.SessionVariables, what: str) -> str:
    return f"code checkout {variables.agent_code_checkout_dir} on {variables.agent_task_branch}: {what}"


def notes_line(variables: contract.SessionVariables, what: str) -> str:
    return f"notes checkout {variables.agent_notes_checkout_dir} on {variables.agent_notes_branch}: {what}"


# --- the checkout status -----------------------------------------------------


def test_both_saved_is_one_line_and_exit_0(checkouts: Checkouts, capsys: pytest.CaptureFixture[str]) -> None:
    variables, _, _ = checkouts

    assert checkout_status(variables, capsys) == (0, "both checkouts are saved on origin\n")


def test_uncommitted_changes_name_the_checkout_its_dir_and_branch(
    checkouts: Checkouts, capsys: pytest.CaptureFixture[str]
) -> None:
    variables, code, _ = checkouts
    (code / "wip.txt").write_text("x\n")

    assert checkout_status(variables, capsys) == (1, code_line(variables, "uncommitted changes") + "\n")


def test_commits_not_pushed_name_the_checkout_its_dir_and_branch(
    checkouts: Checkouts, capsys: pytest.CaptureFixture[str]
) -> None:
    variables, _, notes = checkouts
    commit(notes, f"{TASK.task_notes_dir}/PROGRESS.md", f"{TASK.id}: progress")

    assert checkout_status(variables, capsys) == (1, notes_line(variables, "commits not pushed") + "\n")


def test_both_kinds_in_both_checkouts_give_a_line_each(
    checkouts: Checkouts, capsys: pytest.CaptureFixture[str]
) -> None:
    variables, code, notes = checkouts
    for checkout, name in ((code, "work.txt"), (notes, f"{TASK.task_notes_dir}/PROGRESS.md")):
        commit(checkout, name, f"{TASK.id}: progress")
        (checkout / "wip.txt").write_text("x\n")

    both = "uncommitted changes and commits not pushed"
    assert checkout_status(variables, capsys) == (1, f"{code_line(variables, both)}\n{notes_line(variables, both)}\n")


def test_origin_out_of_reach_is_can_t_tell_not_saved(checkouts: Checkouts, capsys: pytest.CaptureFixture[str]) -> None:
    """The last fetched state says saved here; it is never reported as saved (AC3). The notes checkout is a worktree
    of the code checkout's clone, so it shares origin."""
    variables, code, _ = checkouts
    git(code, "remote", "set-url", "origin", str(code.parent / "missing"))

    exit_code, out = checkout_status(variables, capsys)

    code_status, notes_status = out.splitlines()
    assert exit_code == 1
    assert code_status.startswith(code_line(variables, "can't tell: origin can't be reached: "))
    assert notes_status.startswith(notes_line(variables, "can't tell: origin can't be reached: "))


def test_a_removed_checkout_is_can_t_tell(checkouts: Checkouts, capsys: pytest.CaptureFixture[str]) -> None:
    variables, code, _ = checkouts
    shutil.rmtree(code)

    exit_code, out = checkout_status(variables, capsys)

    assert exit_code == 1
    assert out.startswith(
        code_line(variables, f"can't tell: can't read it: `git -C {code} status --porcelain` failed: ")
    )


def test_git_missing_is_can_t_tell(
    checkouts: Checkouts, tmp_path: Path, process_environment: ProcessEnvironment, capsys: pytest.CaptureFixture[str]
) -> None:
    variables, _, _ = checkouts
    empty = tmp_path / "empty"
    empty.mkdir()
    process_environment.set_env({"PATH": str(empty)})

    missing = "can't tell: can't read it: git not found in PATH"
    assert checkout_status(variables, capsys) == (
        1,
        f"{code_line(variables, missing)}\n{notes_line(variables, missing)}\n",
    )


# --- session-check -----------------------------------------------------------


def test_a_stop_goes_through_when_both_checkouts_are_clean_and_pushed(checkouts: Checkouts) -> None:
    variables, _, _ = checkouts

    assert stop(variables) == ""


def test_a_stop_is_blocked_by_uncommitted_and_unpushed_work(checkouts: Checkouts) -> None:
    variables, code, notes = checkouts
    (code / "wip.txt").write_text("x\n")
    commit(notes, f"{TASK.task_notes_dir}/PROGRESS.md", f"{TASK.id}: progress")

    reason = block_reason(variables)

    assert reason == (
        f"Cannot stop yet: {code_line(variables, 'uncommitted changes')}; "
        f"{notes_line(variables, 'commits not pushed')}. "
        'Commit and push that work (see "Git rules" in AGENTS.md), then finish.'
    )


def test_a_stop_is_blocked_by_commits_left_on_the_branch_after_switching_away(checkouts: Checkouts) -> None:
    """The branch is compared with origin, not only HEAD: a detached HEAD at origin's commit hides nothing."""
    variables, code, _ = checkouts
    commit(code, "work.txt", "feat: work")
    git(code, "switch", "-q", "--detach", f"origin/{TASK.branch}")

    assert code_line(variables, "commits not pushed") in block_reason(variables)


def test_commits_origin_has_but_the_checkout_hasn_t_fetched_count_as_pushed(checkouts: Checkouts) -> None:
    """Pushed to origin's URL rather than to the remote, so origin/<branch> in the checkout stays behind: the
    check fetches it before comparing."""
    variables, code, _ = checkouts
    commit(code, "work.txt", "feat: work")
    origin_url = git(code, "remote", "get-url", "origin").stdout.strip()
    git(code, "-c", "core.hooksPath=/dev/null", "push", "-q", origin_url, f"HEAD:refs/heads/{TASK.branch}")

    assert stop(variables) == ""


def test_a_stop_is_blocked_when_origin_can_t_be_reached(checkouts: Checkouts) -> None:
    """AC8: it compared with the last fetched state before, which says saved here."""
    variables, code, _ = checkouts
    git(code, "remote", "set-url", "origin", str(code.parent / "missing"))

    assert code_line(variables, "can't tell: origin can't be reached: ") in block_reason(variables)


def test_a_stop_is_blocked_when_a_checkout_cant_be_checked(checkouts: Checkouts) -> None:
    """git failing is no evidence that nothing is unsaved."""
    variables, code, _ = checkouts
    shutil.rmtree(code)

    assert code_line(variables, f"can't tell: can't read it: `git -C {code} status --porcelain` failed: ") in (
        block_reason(variables)
    )


def test_a_stop_is_blocked_when_git_is_missing(
    checkouts: Checkouts, tmp_path: Path, process_environment: ProcessEnvironment
) -> None:
    variables, _, _ = checkouts
    empty = tmp_path / "empty"
    empty.mkdir()
    process_environment.set_env({"PATH": str(empty)})

    assert code_line(variables, "can't tell: can't read it: git not found in PATH") in block_reason(variables)


@pytest.mark.parametrize(
    "raw_input", ['{"stop_hook_active": true}', '{"stop_hook_active" : true}', '{\n  "stop_hook_active":\ttrue\n}']
)
def test_a_stop_caused_by_this_hook_blocking_goes_through(checkouts: Checkouts, raw_input: str) -> None:
    """Already looping on this hook: the stop goes through rather than spin, whatever the JSON's spacing. This is
    also how an agent stops when origin can't be reached (AC8)."""
    variables, code, _ = checkouts
    (code / "wip.txt").write_text("x\n")

    assert stop(variables, raw_input) == ""


@pytest.mark.parametrize("raw_input", ["not json", "[]", '{"stop_hook_active": "true"}'])
def test_input_that_is_not_the_looping_flag_still_gets_checked(checkouts: Checkouts, raw_input: str) -> None:
    variables, code, _ = checkouts
    (code / "wip.txt").write_text("x\n")

    assert code_line(variables, "uncommitted changes") in block_reason(variables, raw_input)
