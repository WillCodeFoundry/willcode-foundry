"""The agent's ``task`` command, which agent-kit/bin/task runs: where the task stands, and the next task state.

    task show                       the task state as origin has it: its role, the goal, the events
    task EVENT "<hand-off note>"    write the next task state, and print how to commit and push it

Both read the task state as origin has it, freshly fetched. An event writes the next task state, and the agent's
push of it ends the turn. A refused event writes nothing, and the command runs no git that changes anything.

Runs only in the sandbox: foundry never imports it.
"""

import shlex
import sys
from collections.abc import Sequence
from typing import Final, TextIO

from agent_runtime import contract
from agent_runtime.checkouts import unsaved_work
from agent_runtime.git import Git
from agent_runtime.task.committed import committed_state
from agent_runtime.task.state import (
    END_TURN,
    STATE_FILE,
    TaskState,
    TaskStateRefused,
    commit_subject,
    state_path,
)

USAGE: Final = 'usage: task show | task EVENT "<hand-off note>"'


def task(args: Sequence[str], session: contract.Environ | None = None, out: TextIO | None = None) -> int:
    """Run ``task show`` or ``task EVENT NOTE``; TaskStateRefused, or GitError, says why not."""
    session = session or contract.read_environ()
    out = out or sys.stdout
    match list(args):
        case [] | ["show"]:
            show(session, out)
        case [event, note]:
            send_event(event, note, session, out)
        case _:
            raise TaskStateRefused(USAGE)
    return 0


def show(session: contract.Environ, out: TextIO) -> None:
    """Print the task state as origin has it: its role, and that role's goal and events. The same for every role."""
    task_state = _origin_state(session)
    lines = [f"Task {session.agent_task} ({task_state.lifecycle.name}) is in {task_state.state}. {task_state.standing}"]
    lines += ["", "Hand-off note:", *(f"  {line}" for line in (task_state.note or "(none)").splitlines()), ""]
    if task_state.events:
        whose = f"The {task_state.role}"
        lines += [
            f"{whose}'s goal: {task_state.goal}",
            "",
            f"{whose} ends the turn with one of these events, once the work is pushed:",
            *(f"  {name} → {event.target}: when {event.when}" for name, event in task_state.events.items()),
            "",
            f"  {END_TURN}",
        ]
    print("\n".join(lines), file=out)


def send_event(event: str, note: str, session: contract.Environ, out: TextIO) -> None:
    """Write the task state ``event`` leads to, and print the commands that commit and push it.

    Refuses, writing nothing, while either checkout has unsaved work, while the notes checkout isn't at origin's
    notes branch, or when the transition rule refuses the event.
    """
    if problems := unsaved_work(session):
        raise TaskStateRefused(f"Commit and push your work before sending an event: {'; '.join(problems)}.")
    current_state = _origin_state(session)
    notes_dir, branch = session.agent_notes_dir, session.agent_notes_branch
    notes = Git(notes_dir)
    if notes.current_branch() != branch:
        raise TaskStateRefused(f"The notes checkout isn't on {branch}, so a task state written there can't be pushed.")
    if notes.output("rev-parse", "HEAD") != notes.output("rev-parse", f"origin/{branch}"):
        raise TaskStateRefused(
            f"The notes checkout is behind origin/{branch}. It must be up to date with origin before an event."
        )
    next_state = current_state.after(event, note, session.agent_role)
    path = state_path(session.agent_task_notes_dir)
    (notes_dir / path).write_text(next_state.to_json())
    git_in = ["git", "-C", str(notes_dir)]
    subject = commit_subject(session.agent_task, current_state.state, next_state.state, event)
    lines = [
        f"{current_state.state} → {next_state.state}. Commit and push it to end your turn:",
        f"  {shlex.join([*git_in, 'commit', '--quiet', '--message', subject, '--', path])}",
        f"  {shlex.join([*git_in, 'pull', '--quiet', '--rebase', 'origin', branch])}",
        f"  {shlex.join([*git_in, 'push', '--quiet', 'origin', branch])}",
        _then(next_state),
    ]
    print("\n".join(lines), file=out)


def _then(task_state: TaskState) -> str:
    """What follows once the next task state is pushed."""
    if task_state.role:
        return f"Then it is the {task_state.role}'s turn. Stop once it is pushed."
    return (
        f"Then the task is {task_state.state}, where no role works. Stop once it is pushed, and ask any question your "
        "note holds in the conversation."
    )


def _origin_state(session: contract.Environ) -> TaskState:
    """The task state origin has, freshly fetched; TaskStateRefused when there is none, or it isn't one."""
    notes, branch = Git(session.agent_notes_dir), session.agent_notes_branch
    notes.output("fetch", "--quiet", "origin", branch)
    task_state = committed_state(notes, f"origin/{branch}", state_path(session.agent_task_notes_dir))
    if task_state is None:
        raise TaskStateRefused(
            f"Task {session.agent_task} has no {STATE_FILE} on {branch}. "
            "It was created before task states. Stop here, and tell the human."
        )
    return task_state
