"""The agent's ``task`` command, which agent-kit/bin/task runs: where the task stands, and ending a turn.

    task show                       the task state as origin has it: whose turn, the goal, the events
    task EVENT "<hand-off note>"    end your turn: apply EVENT, then commit and push STATE.json alone

Both read the task state as origin has it, freshly fetched. Ending a turn needs both checkouts clean and pushed
first, the test session-check uses. A push that fails drops the commit, so running the same command again works;
it never retries (ARCHITECTURE.md, design rule 6). Runs only in the sandbox: foundry never imports it.
"""

import sys
from collections.abc import Sequence
from typing import Final, TextIO

from agent_runtime import contract
from agent_runtime.claude_hooks import unsaved_work
from agent_runtime.git import Git
from agent_runtime.task.lifecycles import HUMAN
from agent_runtime.task.state import STATE_FILE, TaskState, TaskStateRefused, not_your_turn

USAGE: Final = 'usage: task show | task EVENT "<hand-off note>"'
TRAILER_KEY: Final = "Task-Event"
"""The trailer naming the event, on each commit the command makes. Written for git log's reader; never checked."""
END_TURN: Final = '"$AGENT_KIT_DIR/bin/task" <event> "<hand-off note>"'


def task(args: Sequence[str], session: contract.Environ | None = None, out: TextIO | None = None) -> int:
    """Run ``task show`` or ``task EVENT NOTE``; TaskStateRefused, or GitError, says why not."""
    session = session or contract.read_environ()
    out = out or sys.stdout
    match list(args):
        case [] | ["show"]:
            show(session, out)
        case [event, note]:
            end_turn(event, note, session, out)
        case _:
            raise TaskStateRefused(USAGE)
    return 0


def show(session: contract.Environ, out: TextIO) -> None:
    """Print the task state as origin has it, and what this role's turn asks of it."""
    task_state = _origin_state(session)
    lifecycle, state = task_state.lifecycle, task_state.definition
    lines = [f"Task {session.agent_task} ({lifecycle.name}) is in {task_state.state}."]
    if task_state.previous:
        lines.append(f"It came from {task_state.previous}.")
    lines += ["", "Hand-off note:", *(f"  {line}" for line in (task_state.note or "(none)").splitlines()), ""]
    if task_state.turn != session.agent_role:
        lines.append(f"It is not your turn: {not_your_turn(task_state, session.agent_role)}. Stop here.")
    else:
        lines += [
            f"It is your turn. Your goal: {state.goal}",
            "",
            "End your turn with one of these events, once your work is pushed:",
            *(f"  {name} → {event.target}: when {event.when}" for name, event in state.events.items()),
            "",
            f"  {END_TURN}",
        ]
    print("\n".join(lines), file=out)


def end_turn(event: str, note: str, session: contract.Environ, out: TextIO) -> None:
    """Apply ``event`` as this role, then commit STATE.json alone, with the event's trailer, and push it."""
    if problems := unsaved_work(session):
        raise TaskStateRefused(f"commit and push your work before ending your turn: {'; '.join(problems)}")
    notes, branch, path = Git(session.agent_notes_dir), session.agent_notes_branch, _state_path(session)
    notes.output("fetch", "--quiet", "origin", branch)
    notes.output("merge", "--ff-only", "--quiet", f"origin/{branch}")
    before = _read(notes, f"HEAD:{path}", session)
    after = before.after(event, session.agent_role, note)
    (session.agent_notes_dir / path).write_text(after.to_json())
    head = notes.output("rev-parse", "HEAD").strip()
    notes.output("add", "--", path)
    subject = f"{session.agent_task}: {before.state} → {after.state} ({event})"
    notes.output("commit", "--quiet", "--message", subject, "--message", f"{TRAILER_KEY}: {event}")
    pushed = notes.run_captured("push", "--quiet", "origin", branch)
    if pushed.returncode != 0:
        notes.output("reset", "--quiet", "--hard", head)
        raise TaskStateRefused(
            f"couldn't push {branch}: {pushed.stderr.strip()}\n"
            "Your turn has not ended, and nothing changed. If another push landed first, run the same command again."
        )
    print(f"{subject}\n{_whose_turn_now(after)}", file=out)


def _whose_turn_now(task_state: TaskState) -> str:
    if task_state.turn is None:
        return f"The task is {task_state.state}. Stop here."
    if task_state.turn == HUMAN:
        return "It is the human's turn now. Stop here, and ask your question in the conversation."
    return f"It is the {task_state.turn}'s turn now. Stop here."


def _state_path(session: contract.Environ) -> str:
    return f"{session.agent_task_notes_dir}/{STATE_FILE}"


def _origin_state(session: contract.Environ) -> TaskState:
    notes, branch = Git(session.agent_notes_dir), session.agent_notes_branch
    notes.output("fetch", "--quiet", "origin", branch)
    return _read(notes, f"origin/{branch}:{_state_path(session)}", session)


def _read(notes: Git, revision_path: str, session: contract.Environ) -> TaskState:
    """The task state at ``<revision>:<path>``; TaskStateRefused when there is none, or it isn't one."""
    if not notes.succeeds("cat-file", "-e", revision_path):
        raise TaskStateRefused(
            f"task {session.agent_task} has no {STATE_FILE} on {session.agent_notes_branch}: "
            "it was created before task states. Stop here, and tell the human."
        )
    return TaskState.parse(notes.output("show", revision_path), revision_path)
