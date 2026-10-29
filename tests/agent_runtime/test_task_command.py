"""agent_runtime.task.command, in-process, against real checkouts session_setup made from a local origin.

The git hooks are off here, except at the end, where the command's own push goes through the built runtime's
pre-push. tests/agent_runtime/test_git_hooks.py tests the STATE.json rule itself, and
tests/agent_kit/test_task_command.py the stub that runs this command.
"""

import io
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
    push_state(notes, TaskState(lifecycle=FEATURE, state="implement", previous="plan", note="TASK.md is approved."))
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
    assert "It came from plan." in shown
    assert "  TASK.md is approved." in shown
    assert "The dev's goal: Implement TASK.md" in shown
    assert "The dev ends the turn with one of these events" in shown
    assert "  submit → review: when every acceptance criterion is met" in shown
    assert "  block → blocked: when you need the human" in shown


def test_show_says_the_same_whichever_role_runs_it(turn: Checkouts) -> None:
    """Round 4's R49: a dev still in its sandbox after submit reads the reviewer's goal and events as the
    reviewer's. show decides nothing about whose turn it is."""
    session, _, notes = turn
    push_state(notes, TaskState(lifecycle=FEATURE, state="review", previous="implement", note="Ready."))

    shown = run(session, "show")

    assert "is in review, assigned to the reviewer." in shown
    assert "The reviewer's goal: Review the task branch" in shown
    assert "The reviewer ends the turn with one of these events" in shown and "  approve → deliver" in shown
    assert "your" not in shown.lower()


def test_show_lists_no_events_for_the_human(turn: Checkouts) -> None:
    session, _, notes = turn
    push_state(notes, TaskState(lifecycle=FEATURE, state="blocked", previous="implement", note="Which base?"))

    shown = run(session, "show")

    assert "is in blocked, assigned to the human." in shown and "goal" not in shown


def test_a_task_without_a_task_state_is_refused(checkouts: Checkouts) -> None:
    session, _, _ = checkouts

    assert "has no STATE.json" in refusal(session, "show")


def test_anything_but_show_or_an_event_and_a_note_is_refused_with_the_usage(turn: Checkouts) -> None:
    session, _, _ = turn

    assert refusal(session, "submit") == 'usage: task show | task EVENT "<hand-off note>"'


# --- ending a turn ------------------------------------------------------------


def test_an_event_commits_and_pushes_the_task_state_alone(turn: Checkouts) -> None:
    session, _, notes = turn

    printed = run(session, "submit", "All criteria met. Start with parser.py.")

    assert origin_state(session) == TaskState(
        lifecycle=FEATURE, state="review", previous="implement", note="All criteria met. Start with parser.py."
    )
    assert printed == f"{TASK.id}: implement → review (submit)\nIt is the reviewer's turn now. Stop here.\n"
    assert git(notes, "show", "--name-only", "--format=", "HEAD").stdout.split() == [STATE_PATH]
    assert git(notes, "log", "-1", "--format=%B").stdout == f"{TASK.id}: implement → review (submit)\n\n"


def test_block_hands_the_task_to_the_human(turn: Checkouts) -> None:
    session, _, _ = turn

    printed = run(session, "block", "Should retries be configurable?")

    assert origin_state(session).assignee == "human"
    assert "The task is assigned to the human now. Stop here, and ask your question in the conversation." in printed


def test_a_move_on_origin_is_picked_up_before_the_event(turn: Checkouts, tmp_path: Path) -> None:
    """The human moved the task back to this role from elsewhere: the notes checkout is behind origin."""
    session, _, notes = turn
    other = tmp_path / "elsewhere"
    git(
        tmp_path,
        "clone",
        "-q",
        "-b",
        session.agent_notes_branch,
        git(notes, "remote", "get-url", "origin").stdout.strip(),
        str(other),
    )
    push_state(other, TaskState(lifecycle=FEATURE, state="deliver", previous="blocked", note="Use main."))

    run(session, "submit", "PR: https://example.com/pr/1")

    assert origin_state(session).state == "done"


def test_a_refused_event_leaves_the_notes_checkout_behind_origin_as_it_was(turn: Checkouts, tmp_path: Path) -> None:
    session, _, notes = turn
    other = tmp_path / "elsewhere"
    url = git(notes, "remote", "get-url", "origin").stdout.strip()
    git(tmp_path, "clone", "-q", "-b", session.agent_notes_branch, url, str(other))
    push_state(other, TaskState(lifecycle=FEATURE, state="implement", previous="blocked", note="Use main."))
    head = git(notes, "rev-parse", "HEAD").stdout

    assert "implement doesn't accept 'approve'" in refusal(session, "approve", "Looks good.")
    assert git(notes, "rev-parse", "HEAD").stdout == head


@pytest.mark.parametrize(
    ("dirty", "problem"),
    [
        ("uncommitted code", "code checkout has uncommitted changes"),
        ("unpushed notes", "notes checkout has commits not pushed"),
    ],
)
def test_unsaved_work_is_refused_and_nothing_changes(turn: Checkouts, dirty: str, problem: str) -> None:
    session, code, notes = turn
    if dirty == "uncommitted code":
        (code / "new.py").write_text("x\n")
    else:
        (notes / TASK.task_notes_dir / "PROGRESS.md").write_text("more\n")
        git(notes, "add", TASK.task_notes_dir)
        git(notes, "commit", "-qm", "progress")

    message = refusal(session, "submit", "done")

    assert message.startswith("commit and push your work before ending your turn:") and problem in message
    assert origin_state(session).state == "implement"


@pytest.mark.parametrize("checkout", [("switch", "-q", "--detach"), ("switch", "-q", "-c", "elsewhere")])
def test_an_event_is_refused_while_the_notes_checkout_is_off_its_branch(
    turn: Checkouts, checkout: tuple[str, ...]
) -> None:
    session, _, notes = turn
    git(notes, *checkout)
    head = git(notes, "rev-parse", "HEAD").stdout

    message = refusal(session, "submit", "All met.")

    assert message.startswith(f"the notes checkout isn't on {session.agent_notes_branch}")
    assert git(notes, "rev-parse", "HEAD").stdout == head
    assert origin_state(session).state == "implement"


def test_a_rejected_push_drops_the_commit_so_the_command_can_run_again(turn: Checkouts) -> None:
    session, _, notes = turn
    origin = Path(git(notes, "remote", "get-url", "origin").stdout.strip().removeprefix("file://"))
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'another push landed first' >&2\nexit 1\n")
    hook.chmod(0o755)
    head = git(notes, "rev-parse", "HEAD").stdout

    message = refusal(session, "submit", "All met.")

    assert "another push landed first" in message and message.endswith("run it again.")
    assert git(notes, "rev-parse", "HEAD").stdout == head
    assert git(notes, "status", "--porcelain").stdout == ""

    hook.unlink()
    run(session, "submit", "All met.")
    assert origin_state(session).state == "review"


# --- through the real hooks ----------------------------------------------------


def hooks_dir(tmp_path: Path, built_kit: Path, pre_commit: str | None = None) -> Path:
    """A hooks dir whose pre-push runs the built runtime's, as the kit's stub does through its link. ``pre_commit``
    adds a pre-commit of the test's own, to make the command's commit fail."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    scripts = {
        "pre-push": f'#!/bin/sh\nexec {sys.executable} -IS {AgentKit(built_kit).runtime} git-hook pre-push "$@"\n'
    }
    if pre_commit:
        scripts["pre-commit"] = pre_commit
    for hook, script in scripts.items():
        (hooks / hook).write_text(script)
        (hooks / hook).chmod(0o755)
    return hooks


def use_hooks(monkeypatch: pytest.MonkeyPatch, session: contract.Environ, hooks: Path) -> None:
    """Point the checkouts' git at ``hooks``, with the session variables a hook reads set as the sandbox sets them."""
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", str(hooks))
    for name in contract.NAMES:
        monkeypatch.setenv(name, str(getattr(session, name.lower())))


def test_the_commands_own_push_passes_the_real_guard(
    turn: Checkouts, built_kit: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, _, _ = turn
    use_hooks(monkeypatch, session, hooks_dir(tmp_path, built_kit))

    run(session, "block", "Which base branch?")

    assert origin_state(session).state == "blocked"


def test_a_refused_commit_leaves_the_notes_checkout_as_it_was(
    turn: Checkouts, built_kit: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, _, notes = turn
    use_hooks(monkeypatch, session, hooks_dir(tmp_path, built_kit, "#!/bin/sh\necho 'signing failed' >&2\nexit 1\n"))
    head = git(notes, "rev-parse", "HEAD").stdout

    message = refusal(session, "submit", "All met.")

    assert message.startswith("couldn't commit STATE.json: signing failed")
    assert git(notes, "rev-parse", "HEAD").stdout == head
    assert git(notes, "status", "--porcelain").stdout == ""
    assert origin_state(session).state == "implement"


def test_an_event_off_the_roles_turn_is_refused_by_the_guard_and_nothing_changes(
    turn: Checkouts, built_kit: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command doesn't check the turn itself: pre-push refuses the change, and the command resets."""
    session, _, notes = turn
    push_state(notes, TaskState(lifecycle=FEATURE, state="review", previous="implement", note="Ready."))
    use_hooks(monkeypatch, session, hooks_dir(tmp_path, built_kit))
    head = git(notes, "rev-parse", "HEAD").stdout

    message = refusal(session, "approve", "Looks good to me.")

    assert "The task is assigned to the reviewer, not the dev." in message
    assert message.endswith("Your turn has not ended, and the notes checkout is as it was. Stop here.")
    assert git(notes, "rev-parse", "HEAD").stdout == head
    assert origin_state(session).state == "review"
