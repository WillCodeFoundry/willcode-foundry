"""The git hooks, which core.hooksPath runs from the kit's hooks/ stubs; git runs them at the checkout's root.

- ``prepare_commit_msg``: the ``Task:`` trailer on every commit on the task branch.
- ``pre_push``: pushes only to this task's branch and the notes branch, and each push judged by what it changes
  there. Task notes stay off the task branch. On the notes branch, a role changes only its own task's notes, and
  its STATE.json only by a legal transition for the role.

pre_push judges what a push changes since origin, not each commit. So every git command that makes commits is
judged alike, and so is a commit made on a detached HEAD or another branch and pushed to one of these.

Each takes what git passes, the session variables and the repository, defaulting to this process's and the
current directory's, and raises GitHookRefused, whose message says what was wrong and what to do instead.
"""

import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

from agent_runtime import contract
from agent_runtime.git import Git
from agent_runtime.task.committed import committed_state
from agent_runtime.task.state import END_TURN, TaskStateRefused, state_path

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
        raise GitHookRefused("prepare-commit-msg: refusing: git passed no message file")
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
    """
    session = session or _read_session("pre-push")
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
                "pre-push",
                f"You may only push {session.agent_task_branch} and {session.agent_notes_branch}, "
                f"not {remote_ref.removeprefix('refs/heads/')}.",
                f"Code goes on {session.agent_task_branch}. Notes go on {session.agent_notes_branch}.",
            )
        changed = _changed_paths(git, remote_sha, local_sha)
        if remote_ref == task_ref:
            _require_no_notes(session, changed)
        else:
            _require_own_notes(session, git, changed, remote_sha, local_sha)


def _changed_paths(git: Git, remote_sha: str, local_sha: str) -> list[str]:
    """Every path the push changes since origin, as git spells it, whatever characters it holds.

    Every kind of change counts, a type change included, and a rename is listed as both its paths. Three pushes
    change nothing to judge:

    - a deletion, which the rulesets refuse;
    - a remote commit this checkout hasn't fetched, which can't be a fast-forward, so the rulesets refuse it;
    - a new branch, which can't happen here: foundry creates both branches before any sandbox starts.
    """
    if local_sha == _ZERO or not git.succeeds("cat-file", "-e", f"{remote_sha}^{{commit}}"):
        return []
    changed = git.output("diff", "--name-only", "--no-renames", "-z", remote_sha, local_sha)
    return [path for path in changed.split("\0") if path]


def _require_no_notes(session: contract.Environ, changed: Sequence[str]) -> None:
    """Refuse task notes on the task branch: nothing under the notes root, at any depth, so notes written from a
    subfolder are caught too."""
    if refused := [path for path in changed if _is_under(session.agent_notes_root, path)]:
        raise _misplaced(
            session.agent_task_branch,
            f"Task notes belong on {session.agent_notes_branch}, in $AGENT_NOTES_DIR/{session.agent_task_notes_dir}/, "
            f"not on {session.agent_task_branch}:",
            refused,
        )


def _require_own_notes(
    session: contract.Environ, git: Git, changed: Sequence[str], remote_sha: str, local_sha: str
) -> None:
    """Refuse a change to the notes branch outside this task's notes dir, and a change to its STATE.json that
    isn't a legal transition for this role."""
    if refused := [path for path in changed if not path.startswith(f"{session.agent_task_notes_dir}/")]:
        raise _misplaced(
            session.agent_notes_branch,
            f"On {session.agent_notes_branch} you may only change files in {session.agent_task_notes_dir}/:",
            refused,
        )
    path = state_path(session.agent_task_notes_dir)
    if path not in changed:
        return
    undo = (
        "",
        "Put it back as origin has it, then commit and push again:",
        f"    git checkout origin/{session.agent_notes_branch} -- {path}",
        f"End your turn with: {END_TURN}",
    )
    # The push carries the new state, not the event: send the event leading to it, and it must give exactly that.
    # Two events leading to one state give the same result.
    try:
        old, new = committed_state(git, remote_sha, path), committed_state(git, local_sha, path)
        if old is None or new is None:
            raise TaskStateRefused(f"It can't be {'created' if old is None else 'deleted'} in the sandbox.")
        if old.turn != session.agent_role:
            raise TaskStateRefused(
                f"It is {old.whose} turn, not the {session.agent_role}'s. The task is in {old.state}."
            )
        leading = [name for name, event in old.definition.events.items() if event.target == new.state]
        if not leading:
            targets = ", ".join(sorted({event.target for event in old.definition.events.values()}))
            raise TaskStateRefused(f"{old.state} can't go to {new.state}. Its events lead to {targets}.")
        if (sent := old.after(leading[0], new.note)) != new:
            raise TaskStateRefused(f"It must read as {leading[0]} leaves it:\n{sent.to_json()}")
    except TaskStateRefused as error:
        raise _refusal("pre-push", f"{path} can't change this way.", *str(error).splitlines(), *undo) from None


def _misplaced(branch: str, rule: str, paths: Sequence[str]) -> GitHookRefused:
    """A refusal of files a push puts where they don't belong, saying how to take them out."""
    return _refusal(
        "pre-push",
        rule,
        *(f"    {path}" for path in paths),
        "",
        "Undo the commits you were pushing, keeping their changes, then commit only what belongs:",
        f"    git reset origin/{branch}",
    )


def _refusal(hook: str, *lines: str) -> GitHookRefused:
    """Every refusal's shape: the hook, what was wrong, then what to do instead."""
    body = "".join(f"  {line}\n" for line in lines)
    return GitHookRefused(f"{hook}: refusing\n\n{body}")


def _read_session(hook: str) -> contract.Environ:
    """The session variables, or a refusal naming the missing ones."""
    try:
        return contract.read_environ()
    except contract.MissingVariables as error:
        raise GitHookRefused(f"{hook}: {error}") from None


def _is_under(root: str, path: str) -> bool:
    """Whether ``path`` sits in a folder named ``root``, at any depth."""
    root_parts, folders = PurePosixPath(root).parts, PurePosixPath(path).parts[:-1]
    return any(folders[i : i + len(root_parts)] == root_parts for i in range(len(folders)))
