"""The agent's ``task`` command, which agent-kit/bin/task runs: where the task stands, and ending a turn.

    task show                       the task state as origin has it: its assignee, the goal, the events
    task EVENT "<hand-off note>"    end your turn: apply EVENT, then commit and push STATE.json alone

Both read the task state as origin has it, freshly fetched. Ending a turn needs both checkouts clean and pushed
first, the test session-check uses. A refused event, or a git step that fails, leaves the notes checkout as it was.
Running the same command again then works, and it never retries (ARCHITECTURE.md, design rule 6).

Runs only in the sandbox: foundry never imports it.
"""

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final, TextIO

from agent_runtime import contract
from agent_runtime.checkouts import unsaved_work
from agent_runtime.git import Git
from agent_runtime.task.committed import committed_state
from agent_runtime.task.state import END_TURN, STATE_FILE, TaskState, TaskStateRefused, state_path

USAGE: Final = 'usage: task show | task EVENT "<hand-off note>"'


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
    """Print the task state as origin has it, and what its turn asks for."""
    task_state = _origin_state(session)
    lifecycle, state = task_state.lifecycle, task_state.definition
    lines = [f"Task {session.agent_task} ({lifecycle.name}) is in {task_state.state}."]
    if task_state.previous:
        lines.append(f"It came from {task_state.previous}.")
    lines += ["", "Hand-off note:", *(f"  {line}" for line in (task_state.note or "(none)").splitlines()), ""]
    if state.events:
        lines += [
            f"The goal: {state.goal}",
            "",
            "End the turn with one of these events, once its work is pushed:",
            *(f"  {name} → {event.target}: when {event.when}" for name, event in state.events.items()),
            "",
            f"  {END_TURN}",
        ]
    print("\n".join(lines), file=out)


def end_turn(event: str, note: str, session: contract.Environ, out: TextIO) -> None:
    """Apply ``event``, then commit STATE.json alone and push it."""
    notes, branch, path = (
        Git(session.agent_notes_dir),
        session.agent_notes_branch,
        state_path(session.agent_task_notes_dir),
    )
    if notes.current_branch() != branch:
        raise TaskStateRefused(
            f"the notes checkout isn't on {branch}, so ending your turn would push nothing. "
            f"Run git switch {branch} in $AGENT_NOTES_DIR, then this command again."
        )
    if problems := unsaved_work(session):
        raise TaskStateRefused(f"commit and push your work before ending your turn: {'; '.join(problems)}")
    found = notes.output("rev-parse", "HEAD").strip()
    before = _origin_state(session)
    after = before.after(event, note)
    subject = after.commit_subject(session.agent_task, event)
    if failure := _commit_and_push(notes, branch, session.agent_notes_dir / path, after, subject):
        notes.output("reset", "--quiet", "--hard", found)
        raise TaskStateRefused(
            f"couldn't {failure}\n"
            "Your turn has not ended, and the notes checkout is as it was. "
            "If another push landed first, run the same command again."
        )
    print(f"{subject}\n{_assigned_now(after)}", file=out)


def _commit_and_push(notes: Git, branch: str, state_file: Path, after: TaskState, subject: str) -> str | None:
    """Bring in origin's notes, then commit ``after`` alone and push it; the step that failed and why, or None.

    Run only once ``after`` is known to be allowed, so a refused event never moves the checkout.
    """
    merged = notes.run_captured("merge", "--ff-only", "--quiet", f"origin/{branch}")
    if merged.returncode != 0:
        return f"bring in origin/{branch}: {(merged.stderr or merged.stdout).strip()}"
    state_file.write_text(after.to_json())
    steps = [
        ("commit STATE.json", ("commit", "--quiet", "--message", subject, "--", str(state_file))),
        (f"push {branch}", ("push", "--quiet", "origin", branch)),
    ]
    for step, args in steps:
        result = notes.run_captured(*args)
        if result.returncode != 0:
            return f"{step}: {(result.stderr or result.stdout).strip()}"
    return None


def _assigned_now(task_state: TaskState) -> str:
    if task_state.role:
        return f"It is the {task_state.role}'s turn now. Stop here."
    if task_state.assigned_to_human:
        return "The task is assigned to the human now. Stop here, and ask your question in the conversation."
    return f"The task is {task_state.state}, assigned to no one. Stop here."


def _origin_state(session: contract.Environ) -> TaskState:
    """The task state origin has, freshly fetched; TaskStateRefused when there is none, or it isn't one."""
    notes, branch = Git(session.agent_notes_dir), session.agent_notes_branch
    notes.output("fetch", "--quiet", "origin", branch)
    task_state = committed_state(notes, f"origin/{branch}", state_path(session.agent_task_notes_dir))
    if task_state is None:
        raise TaskStateRefused(
            f"task {session.agent_task} has no {STATE_FILE} on {branch}: "
            "it was created before task states. Stop here, and tell the human."
        )
    return task_state
