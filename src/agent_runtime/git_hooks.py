"""The git hooks, which core.hooksPath runs from the kit's hooks/ stubs; git runs them at the checkout's root.

- ``prepare_commit_msg``: the ``Task:`` trailer on every commit on the task branch.
- ``pre_push``: pushes only to this task's branch and the notes branch, and each push judged by what it changes
  there. Task notes stay off the task branch. On the notes branch, a role changes only its own task's notes, and
  its STATE.json only by a legal transition for the role.

pre_push judges what a push brings to origin, so every git command that makes commits is judged alike. The paths
every pushed commit touches, and those the push leaves changed, must belong there, since they stay in the
branch's history. STATE.json is judged by what the push leaves.

Each takes what git passes, the session variables and the repository, defaulting to this process's and the
current directory's. Each raises GitHookRefused, whose message says what is wrong and which rule it breaks. The
agent fixes it with ordinary git, and pre-push judges the next push again.
"""

import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Final

from agent_runtime import contract
from agent_runtime.git import Git
from agent_runtime.task.committed import committed_state
from agent_runtime.task.state import END_TURN, TaskStateRefused, state_path

REFUSING: Final = ": refusing"
"""What follows a hook's name at the start of each of its refusals."""

PRE_PUSH: Final = "pre-push"
"""The hook that judges every push, as git names it."""

_ZERO = "0" * 40
"""The sha git passes for a ref that doesn't exist on one side of a push."""


class GitHookRefused(Exception):
    """A hook refuses: the message is the whole refusal, as the agent will read it."""


def prepare_commit_msg(
    args: Sequence[str] | None = None, session: contract.Environ | None = None, git: Git | None = None
) -> None:
    """Add a "Task: <task>" trailer to every commit on the task branch, so each code commit traces back to
    its task without the agent having to remember. Runs even with --no-verify. git passes the message
    file first."""
    session = session or _read_session("prepare-commit-msg")
    git = git or Git()
    arguments = sys.argv[1:] if args is None else args
    if git.current_branch() != session.agent_task_branch:
        return
    if not arguments:
        raise _refusal("prepare-commit-msg", "git passed no message file.")
    message_file = arguments[0]
    # An empty message aborts the commit; a trailer would make it go through.
    if not git.output("stripspace", "--strip-comments", input=Path(message_file).read_text()):
        return
    trailer = f"Task: {session.agent_task}"
    git.output("interpret-trailers", "--in-place", "--if-exists", "doNothing", "--trailer", trailer, message_file)


def pre_push(
    refs: Iterable[str] | None = None, session: contract.Environ | None = None, git: Git | None = None
) -> None:
    """Refuse a push to anything but this task's branch and the notes branch, or one that changes there what this
    role may not.

    The project's GitHub rulesets allow any task branch, since GitHub can't tell one task from another;
    this keeps a role to its own. git passes one line per ref on stdin:
    ``<local ref> <local sha> <remote ref> <remote sha>``.

    A path counts if any pushed commit touches it, or if the push leaves it changed. STATE.json is judged by
    what the push leaves. ADR 0011 says why, and ``_paths_to_judge`` which pushes have nothing to judge.
    """
    session = session or _read_session(PRE_PUSH)
    git = git or Git()
    task_ref, notes_ref = f"refs/heads/{session.agent_task_branch}", f"refs/heads/{session.agent_notes_branch}"
    for line in sys.stdin if refs is None else refs:
        match line.split():
            case []:
                continue
            case [_local_ref, local_sha, remote_ref, remote_sha]:
                pass
            case _:
                local_sha = remote_ref = remote_sha = ""
        if remote_ref not in (task_ref, notes_ref):
            raise _refusal(
                PRE_PUSH,
                f"You may only push {session.agent_task_branch} and {session.agent_notes_branch}, "
                f"not {remote_ref.removeprefix('refs/heads/')}.",
                f"Code goes on {session.agent_task_branch}. Notes go on {session.agent_notes_branch}.",
            )
        if not (paths := _paths_to_judge(git, remote_sha, local_sha)):
            continue
        touched, net_changed = paths
        if remote_ref == task_ref:
            _require_no_notes(session, touched)
        else:
            _require_own_notes(session, git, touched, net_changed, remote_sha, local_sha)


def _paths_to_judge(git: Git, remote_sha: str, local_sha: str) -> tuple[list[str], list[str]] | None:
    """Every path a pushed commit touches or the push changes overall, then those it changes overall. None for
    a push with nothing to judge:

    - a deletion, which the rulesets refuse;
    - a remote commit this checkout hasn't fetched, which can't be a fast-forward, so the rulesets refuse it;
    - a new branch, since there is nothing to compare it with.

    foundry creates both branches before any sandbox starts. So a new branch is a task branch pushed again after
    its pull request merged and it was deleted, a rare mistake this guardrail lets through.
    """
    if local_sha == _ZERO or not git.succeeds("cat-file", "-e", f"{remote_sha}^{{commit}}"):
        return None
    net_changed = _paths(git, "diff", "--name-only", "--no-renames", "-z", remote_sha, local_sha)
    pushed = _paths(git, "log", "--format=", "--name-only", "--no-renames", "-z", local_sha, f"^{remote_sha}")
    return list(dict.fromkeys([*pushed, *net_changed])), net_changed


def _paths(git: Git, *args: str) -> list[str]:
    """The paths a git command lists, NUL-separated, as git spells them, whatever characters they hold."""
    return [path for path in git.output(*args).split("\0") if path]


def _require_no_notes(session: contract.Environ, touched: Sequence[str]) -> None:
    """Refuse task notes on the task branch: nothing under the notes root, at any depth, so notes written from a
    subfolder are caught too."""
    if refused := [path for path in touched if _is_under(session.agent_notes_root, path)]:
        raise _refusal(
            PRE_PUSH,
            f"These are task notes, so they can't be pushed to {session.agent_task_branch}:",
            *(f"    {path}" for path in refused),
            f"Task notes belong on {session.agent_notes_branch}, in $AGENT_NOTES_DIR/{session.agent_task_notes_dir}/.",
            "No commit you push to the task branch may touch them.",
        )


def _require_own_notes(
    session: contract.Environ,
    git: Git,
    touched: Sequence[str],
    net_changed: Sequence[str],
    remote_sha: str,
    local_sha: str,
) -> None:
    """Refuse a change to the notes branch outside this task's task notes dir, and a change to its STATE.json that
    isn't a legal transition for this role."""
    if refused := [path for path in touched if not path.startswith(f"{session.agent_task_notes_dir}/")]:
        raise _refusal(
            PRE_PUSH,
            f"These are outside your task notes dir, {session.agent_task_notes_dir}/, so they can't be pushed:",
            *(f"    {path}" for path in refused),
            f"On {session.agent_notes_branch}, no commit you push may touch another task's notes.",
        )
    path = state_path(session.agent_task_notes_dir)
    # What the push leaves is judged, so a change a later pushed commit undoes passes.
    if path not in net_changed:
        return
    rule = f"Only the task command changes it, on your turn ({END_TURN}), and the push must leave it as written."
    try:
        old_state, new_state = committed_state(git, remote_sha, path), committed_state(git, local_sha, path)
        if old_state is None or new_state is None:
            raise TaskStateRefused(f"It can't be {'created' if old_state is None else 'deleted'} in the sandbox.")
        # The push carries the new task state, not the event. So send the event leading to it, by the same rule
        # as the task command.
        if new_state.lifecycle != old_state.lifecycle:
            raise TaskStateRefused(f"The lifecycle can't change. It is {old_state.lifecycle.name}.")
        event = old_state.event_to(new_state.state)
        if old_state.after(event, new_state.note, session.agent_role) != new_state:
            raise TaskStateRefused(f"It must read exactly as {event} leaves it, with no space around the note.")
    except TaskStateRefused as error:
        raise _refusal(PRE_PUSH, f"{path} can't change this way.", *str(error).splitlines(), rule) from None


def _refusal(hook: str, *lines: str) -> GitHookRefused:
    """Every refusal's shape: the hook, what is wrong, and the rule it breaks. The agent fixes it with git."""
    body = "".join(f"  {line}\n" for line in lines)
    return GitHookRefused(f"{hook}{REFUSING}\n\n{body}")


def _read_session(hook: str) -> contract.Environ:
    """The session variables, or a refusal naming the missing ones."""
    try:
        return contract.read_environ()
    except contract.MissingVariables as error:
        raise _refusal(hook, str(error)) from None


def _is_under(root: str, path: str) -> bool:
    """Whether ``path`` sits in a folder named ``root``, at any depth."""
    root_parts, folders = PurePosixPath(root).parts, PurePosixPath(path).parts[:-1]
    return any(folders[i : i + len(root_parts)] == root_parts for i in range(len(folders)))
