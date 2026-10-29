"""agent_runtime.task.command, in-process, against real checkouts session_setup made from a local origin.

The git hooks are off here, except at the end, where the commands an event prints push through the built
runtime's pre-push. tests/agent_runtime/test_git_hooks.py tests pre-push itself, and
tests/agent_kit/test_task_command.py the stub that runs this command.
"""

import io
import subprocess
import sys
from pathlib import Path

import pytest

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit
from agent_runtime.task.command import task
from agent_runtime.task.lifecycles import FEATURE
from agent_runtime.task.state import TaskState, TaskStateRefused
from tests.support import TASK, git

STATE_PATH = f"{TASK.task_notes_dir}/STATE.json"

Checkouts = tuple[contract.Environ, Path, Path]


@pytest.fixture
def turn(checkouts: Checkouts, monkeypatch: pytest.MonkeyPatch) -> Checkouts:
    """The checkouts, with hooks off, and the task in implement: the dev's turn, which is this session's role."""
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "/dev/null")
    session, _, notes = checkouts
    assert session.agent_role == "dev"
    push_state(notes, TaskState(lifecycle=FEATURE, state="implement", note="TASK.md is approved."))
    return checkouts


def push_state(notes: Path, task_state: TaskState) -> None:
    """Commit and push a task state from the notes checkout: setup, or another role's or the human's move."""
    (notes / STATE_PATH).write_text(task_state.to_json())
    git(notes, "add", STATE_PATH)
    git(notes, "commit", "-qm", f"state: {task_state.state}")
    git(notes, "push", "-q", "origin", "HEAD")


def origin_state(session: contract.Environ) -> TaskState:
    shown = git(session.agent_notes_dir, "show", f"origin/{session.agent_notes_branch}:{STATE_PATH}").stdout
    return TaskState.parse(shown, STATE_PATH)


def run(session: contract.Environ, *args: str) -> str:
    out = io.StringIO()
    assert task(args, session, out) == 0
    return out.getvalue()


def refusal(session: contract.Environ, *args: str) -> str:
    with pytest.raises(TaskStateRefused) as refused:
        task(args, session, io.StringIO())
    return str(refused.value)


# --- show ---------------------------------------------------------------------


def test_show_names_the_assignee_their_goal_their_events_and_the_note(turn: Checkouts) -> None:
    session, _, _ = turn

    shown = run(session, "show")

    assert f"Task {TASK.id} (feature) is in implement, assigned to the dev." in shown
    assert "came from" not in shown
    assert "  TASK.md is approved." in shown
    assert "The dev's goal: Implement TASK.md" in shown
    assert "The dev ends the turn with one of these events" in shown
    assert "  submit → review: when every acceptance criterion is met" in shown
    assert "  block → blocked: when you need the human" in shown


def test_show_says_the_same_whichever_role_runs_it(turn: Checkouts) -> None:
    """Round 4's R49: a dev still in its sandbox after submit reads the reviewer's goal and events as the
    reviewer's. show decides nothing about whose turn it is."""
    session, _, notes = turn
    push_state(notes, TaskState(lifecycle=FEATURE, state="review", note="Ready."))

    shown = run(session, "show")

    assert "is in review, assigned to the reviewer." in shown
    assert "The reviewer's goal: Review the task branch" in shown
    assert "The reviewer ends the turn with one of these events" in shown and "  approve → deliver" in shown
    assert "your" not in shown.lower()


def test_show_lists_no_events_for_the_human(turn: Checkouts) -> None:
    session, _, notes = turn
    push_state(notes, TaskState(lifecycle=FEATURE, state="blocked", note="Which base?"))

    shown = run(session, "show")

    assert "is in blocked, assigned to the human." in shown and "goal" not in shown


def test_a_task_without_a_task_state_is_refused(checkouts: Checkouts) -> None:
    session, _, _ = checkouts

    assert "has no STATE.json" in refusal(session, "show")


def test_anything_but_show_or_an_event_and_a_note_is_refused_with_the_usage(turn: Checkouts) -> None:
    session, _, _ = turn

    assert refusal(session, "submit") == 'usage: task show | task EVENT "<hand-off note>"'


# --- an event -----------------------------------------------------------------


def written_state(notes: Path) -> TaskState:
    return TaskState.parse((notes / STATE_PATH).read_text(), STATE_PATH)


def nothing_written(session: contract.Environ, notes: Path) -> bool:
    return git(notes, "status", "--porcelain").stdout == "" and origin_state(session).state == "implement"


def commands(printed: str) -> list[str]:
    """The git commands an event prints, as the agent would copy them."""
    return [line.strip() for line in printed.splitlines() if "git -C " in line]


def test_an_event_writes_the_next_task_state_and_prints_how_to_end_the_turn(turn: Checkouts) -> None:
    session, _, notes = turn

    printed = run(session, "submit", "All criteria met. Start with parser.py.")

    assert written_state(notes) == TaskState(
        lifecycle=FEATURE, state="review", note="All criteria met. Start with parser.py."
    )
    assert origin_state(session).state == "implement"
    git_in = f"git -C {notes}"
    assert printed == (
        "implement → review. Commit and push it to end your turn:\n"
        f"  {git_in} commit --quiet --message '{TASK.id}: implement → review (submit)' -- {STATE_PATH}\n"
        f"  {git_in} pull --quiet --rebase origin {session.agent_notes_branch}\n"
        f"  {git_in} push --quiet origin {session.agent_notes_branch}\n"
        "Then it is the reviewer's turn. Stop once it is pushed.\n"
    )


def test_block_hands_the_task_to_the_human(turn: Checkouts) -> None:
    session, _, notes = turn

    printed = run(session, "block", "Should retries be configurable?")

    assert written_state(notes).assignee == "human"
    assert printed.endswith(
        "Then the task is assigned to the human. Once it is pushed, stop, and ask your question in the conversation.\n"
    )


def test_an_event_off_the_roles_turn_is_refused_by_the_transition_rule(turn: Checkouts) -> None:
    """The rule in TaskState.after is the command's only check of the turn. approve is an event review accepts,
    so only the rule's assignee check refuses it."""
    session, _, notes = turn
    push_state(notes, TaskState(lifecycle=FEATURE, state="review", note="Ready."))

    assert (
        refusal(session, "approve", "Looks good.")
        == "The task is assigned to the reviewer, not the dev. It is in review."
    )
    assert git(notes, "status", "--porcelain").stdout == ""


def test_an_event_the_state_doesnt_accept_is_refused_writing_nothing(turn: Checkouts) -> None:
    session, _, notes = turn

    assert "implement doesn't accept 'approve'" in refusal(session, "approve", "Looks good.")
    assert nothing_written(session, notes)


@pytest.mark.parametrize(
    ("dirty", "problem"),
    [
        ("uncommitted code", "code checkout has uncommitted changes"),
        ("unpushed notes", "notes checkout has commits not pushed"),
    ],
)
def test_unsaved_work_is_refused_writing_nothing(turn: Checkouts, dirty: str, problem: str) -> None:
    session, code, notes = turn
    if dirty == "uncommitted code":
        (code / "new.py").write_text("x\n")
    else:
        (notes / TASK.task_notes_dir / "PROGRESS.md").write_text("more\n")
        git(notes, "add", TASK.task_notes_dir)
        git(notes, "commit", "-qm", "progress")

    message = refusal(session, "submit", "done")

    assert message.startswith("Commit and push your work before sending an event:") and problem in message
    assert written_state(notes).state == "implement"


@pytest.mark.parametrize("checkout", [("switch", "-q", "--detach"), ("switch", "-q", "-c", "elsewhere")])
def test_an_event_is_refused_while_the_notes_checkout_is_off_its_branch(
    turn: Checkouts, checkout: tuple[str, ...]
) -> None:
    session, _, notes = turn
    git(notes, *checkout)

    message = refusal(session, "submit", "All met.")

    assert message == (
        f"The notes checkout isn't on {session.agent_notes_branch}, so a task state written there can't be pushed."
    )
    assert nothing_written(session, notes)


def test_an_event_is_refused_while_the_notes_checkout_is_behind_origin(turn: Checkouts, tmp_path: Path) -> None:
    """The human moved the task from elsewhere. Written on the old checkout, the task state wouldn't reach origin."""
    session, _, notes = turn
    other = tmp_path / "elsewhere"
    url = git(notes, "remote", "get-url", "origin").stdout.strip()
    git(tmp_path, "clone", "-q", "-b", session.agent_notes_branch, url, str(other))
    push_state(other, TaskState(lifecycle=FEATURE, state="deliver", note="Use main."))

    message = refusal(session, "submit", "PR: https://example.com/pr/1")

    assert message == (
        f"The notes checkout is behind origin/{session.agent_notes_branch}. "
        "It must be up to date with origin before an event."
    )
    assert git(notes, "status", "--porcelain").stdout == ""


# --- through the real pre-push ----------------------------------------------------


def use_pre_push(monkeypatch: pytest.MonkeyPatch, session: contract.Environ, tmp_path: Path, built_kit: Path) -> None:
    """Point the checkouts' git at a pre-push that runs the built runtime's, as the kit's stub does through its
    link, with the session variables a hook reads set as the sandbox sets them."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    pre_push = hooks / "pre-push"
    pre_push.write_text(f'#!/bin/sh\nexec {sys.executable} -IS {AgentKit(built_kit).runtime} git-hook pre-push "$@"\n')
    pre_push.chmod(0o755)
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", str(hooks))
    for name in contract.NAMES:
        monkeypatch.setenv(name, str(getattr(session, name.lower())))


@pytest.mark.parametrize(("event", "state"), [("submit", "review"), ("block", "blocked")])
def test_the_printed_commands_push_what_the_real_pre_push_accepts(
    turn: Checkouts, built_kit: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, event: str, state: str
) -> None:
    session, _, notes = turn
    use_pre_push(monkeypatch, session, tmp_path, built_kit)
    printed = run(session, event, "Over to you.")

    for command in commands(printed)[:3]:
        subprocess.run(["sh", "-c", command], cwd=tmp_path, check=True, capture_output=True)

    assert origin_state(session).state == state
    assert git(notes, "log", "-1", "--format=%s").stdout.strip() == f"{TASK.id}: implement → {state} ({event})"


def test_the_printed_commands_still_push_after_another_task_pushed(
    turn: Checkouts, built_kit: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Other roles push to the notes branch at the same time, so the printed pull --rebase brings theirs in."""
    session, _, notes = turn
    printed = run(session, "submit", "All met.")
    other = tmp_path / "other-role"
    url = git(notes, "remote", "get-url", "origin").stdout.strip()
    git(tmp_path, "clone", "-q", "-b", session.agent_notes_branch, url, str(other))
    (other / ".agent" / "t2").mkdir(parents=True)
    (other / ".agent" / "t2" / "PROGRESS.md").write_text("theirs\n")
    git(other, "add", ".agent")
    git(other, "commit", "-qm", "t2: progress")
    git(other, "push", "-q", "origin", "HEAD")
    use_pre_push(monkeypatch, session, tmp_path, built_kit)

    for command in commands(printed)[:3]:
        subprocess.run(["sh", "-c", command], cwd=tmp_path, check=True, capture_output=True)

    assert origin_state(session).state == "review"


def test_a_human_move_before_the_push_stops_the_pull_and_loses_no_work(turn: Checkouts, tmp_path: Path) -> None:
    """Round 5's R59: the printed pull --rebase stops on STATE.json, and says so. AGENTS.md tells the agent that
    means the human moved the task, and to stop. Aborting the rebase gives back exactly the agent's commit."""
    session, _, notes = turn
    printed = run(session, "submit", "All met.")
    human = tmp_path / "human"
    url = git(notes, "remote", "get-url", "origin").stdout.strip()
    git(tmp_path, "clone", "-q", "-b", session.agent_notes_branch, url, str(human))
    push_state(human, TaskState(lifecycle=FEATURE, state="blocked", note="Wait for me."))
    commit, pull, _ = commands(printed)

    subprocess.run(["sh", "-c", commit], check=True, capture_output=True)
    agents_commit = git(notes, "rev-parse", "HEAD").stdout
    pulled = subprocess.run(["sh", "-c", pull], check=False, capture_output=True, text=True)

    assert pulled.returncode != 0 and STATE_PATH in pulled.stdout + pulled.stderr
    assert origin_state(session).state == "blocked"
    git(notes, "rebase", "--abort")
    assert git(notes, "rev-parse", "HEAD").stdout == agents_commit
    assert written_state(notes).state == "review"
