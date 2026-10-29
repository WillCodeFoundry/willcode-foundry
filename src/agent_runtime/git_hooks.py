"""The git hooks, which core.hooksPath runs from the kit's hooks/ stubs; git runs them at the checkout's root.

- ``prepare_commit_msg``: the ``Task:`` trailer on every commit on the task branch.
- ``pre_push``: pushes only to this task's branch and the notes branch, and each push judged by what it changes
  there. Task notes stay off the task branch. On the notes branch, a role changes only its own task's notes, and
  its STATE.json only by a legal transition for the role.

pre_push judges what a push brings to origin, so every git command that makes commits is judged alike. The paths
every pushed commit touches, and those the push leaves changed, must belong there, since they stay in the
branch's history. STATE.json is judged by what the push leaves.

Each takes what git passes, the session variables and the repository, defaulting to this process's and the
current directory's, and raises GitHookRefused, whose message says what was wrong and what to do instead.
"""

import shlex
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Final

from agent_runtime import contract
from agent_runtime.git import Git
from agent_runtime.task.committed import committed_state
from agent_runtime.task.state import END_TURN, TaskStateRefused, require_legal_transition, state_path

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
            _require_no_notes(session, touched, net_changed, remote_sha)
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


def _require_no_notes(
    session: contract.Environ, touched: Sequence[str], net_changed: Sequence[str], remote_sha: str
) -> None:
    """Refuse task notes on the task branch: nothing under the notes root, at any depth, so notes written from a
    subfolder are caught too."""
    if refused := [path for path in touched if _is_under(session.agent_notes_root, path)]:
        raise _refusal(
            PRE_PUSH,
            f"Task notes belong on {session.agent_notes_branch}, in $AGENT_NOTES_DIR/{session.agent_task_notes_dir}/, "
            f"not on {session.agent_task_branch}:",
            *(f"    {path}" for path in refused),
            "",
            "Copy anything you still need to $AGENT_NOTES_DIR first.",
            *_put_back(contract.PROJECT_DIR, remote_sha, refused, net_changed),
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
            f"On {session.agent_notes_branch} you may only change files in {session.agent_task_notes_dir}/:",
            *(f"    {path}" for path in refused),
            "",
            *_put_back(contract.NOTES_DIR, remote_sha, refused, net_changed),
        )
    path = state_path(session.agent_task_notes_dir)
    # What the push leaves is judged, so a change a later pushed commit undoes passes.
    if path not in net_changed:
        return
    undo = (
        "",
        "If you changed it by hand, put it back.",
        *_put_back(contract.NOTES_DIR, remote_sha, [path], net_changed),
        f"Only the task command changes it, when it is your turn: {END_TURN}",
    )
    try:
        old, new = committed_state(git, remote_sha, path), committed_state(git, local_sha, path)
        if old is None or new is None:
            raise TaskStateRefused(f"It can't be {'created' if old is None else 'deleted'} in the sandbox.")
        require_legal_transition(old, new, session.agent_role)
    except TaskStateRefused as error:
        raise _refusal(PRE_PUSH, f"{path} can't change this way.", *str(error).splitlines(), *undo) from None


def _put_back(checkout: str, remote_sha: str, refused: Sequence[str], net_changed: Sequence[str]) -> tuple[str, ...]:
    """How to undo a refused push, from ``remote_sha``, the commit it was judged against. Origin may have moved
    since. Undo the pushed commits, keeping their changes staged, then put back each refused path the push changes
    overall.

    A path added and removed within the push is gone once the commits are undone, so it needs no putting back.
    ``checkout`` is the variable naming the checkout, so the commands act on it from any directory, with paths
    from its root.
    """
    git_in = f'git -C "${checkout}"'
    put_back = [path for path in refused if path in net_changed]
    restore = (
        (
            "Put these back as they were:",
            f"    {git_in} restore --source={remote_sha} --staged --worktree -- {shlex.join(put_back)}",
        )
        if put_back
        else ()
    )
    return (
        "Undo the commits you were pushing, keeping their changes, which folds them into one commit:",
        f"    {git_in} reset --soft {remote_sha}",
        *restore,
        "Then commit what is left, pull --rebase, and push again.",
    )


def _refusal(hook: str, *lines: str) -> GitHookRefused:
    """Every refusal's shape: the hook, what was wrong, then what to do instead."""
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
