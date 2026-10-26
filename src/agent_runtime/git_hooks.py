"""The git hooks, which core.hooksPath runs from the kit's hooks/ stubs; git runs them at the checkout's root.

- ``pre_commit``: what each checkout may commit, so tasks don't step on each other.
- ``prepare_commit_msg``: the ``Task:`` trailer on every commit on the task branch.
- ``pre_push``: pushes only to this task's branch and the notes branch.

Each takes what git passes, and the session variables, defaulting to this process's.
"""

import subprocess
import sys
from collections.abc import Iterable, Sequence

from agent_runtime import contract
from agent_runtime.refusal import current_branch, refuse


def pre_commit(env: contract.Environ | None = None) -> None:
    """Refuse a commit that puts files where they don't belong.

    task branch: no task notes: nothing under the notes root, at any depth, so notes written from a
                 subfolder are caught too;
    notes branch: only this task's notes folder.
    Commits on any other branch are left alone: they can't be pushed.
    """
    environ = env or _read_environ("pre-commit")
    branch = current_branch()
    if branch == environ.task_branch:
        root = environ.notes_root
        refused = [path for path in _staged_paths() if path.startswith(f"{root}/") or f"/{root}/" in path]
        rule = (
            f"Task notes belong on {environ.notes_branch}, in $AGENT_NOTES_DIR/{environ.task_notes}/, "
            f"not on {environ.task_branch}:"
        )
    elif branch == environ.notes_branch:
        refused = [path for path in _staged_paths() if not path.startswith(f"{environ.task_notes}/")]
        rule = f"On {environ.notes_branch} you may only change files in {environ.task_notes}/:"
    else:
        return
    if refused:
        refuse(
            "pre-commit", rule, *(f"    {path}" for path in refused), "", "Unstage with: git restore --staged <file>"
        )


def prepare_commit_msg(args: Sequence[str] | None = None, env: contract.Environ | None = None) -> None:
    """Add a "Task: <task>" trailer to every commit on the task branch, so each code commit traces back to
    its task without the agent having to remember. Runs even with --no-verify. git passes the message
    file first."""
    environ = env or _read_environ("prepare-commit-msg")
    arguments = sys.argv[1:] if args is None else args
    if current_branch() != environ.task_branch:
        return
    if not arguments:
        sys.exit("prepare-commit-msg needs the message file")
    message_file = arguments[0]
    # An empty message aborts the commit; a trailer would make it go through.
    with open(message_file) as message:
        stripped = subprocess.run(
            ["git", "stripspace", "--strip-comments"], stdin=message, capture_output=True, text=True, check=True
        )
    if not stripped.stdout:
        return
    trailer = f"Task: {environ.task}"
    subprocess.run(
        ["git", "interpret-trailers", "--in-place", "--if-exists", "doNothing", "--trailer", trailer, message_file],
        check=True,
    )


def pre_push(refs: Iterable[str] | None = None, env: contract.Environ | None = None) -> None:
    """Refuse a push to anything but this task's branch and the notes branch.

    The project's GitHub rulesets allow any task branch, since GitHub can't tell one task from another;
    this keeps a role to its own. git passes one line per ref on stdin:
    ``<local ref> <local sha> <remote ref> <remote sha>``.
    """
    environ = env or _read_environ("pre-push")
    allowed = {f"refs/heads/{environ.task_branch}", f"refs/heads/{environ.notes_branch}"}
    for line in sys.stdin if refs is None else refs:
        fields = line.split()
        if not fields:
            continue
        remote_ref = fields[2] if len(fields) > 2 else ""
        if remote_ref not in allowed:
            refuse(
                "pre-push",
                f"You may only push {environ.task_branch} and {environ.notes_branch}, "
                f"not {remote_ref.removeprefix('refs/heads/')}.",
                f"Code goes on {environ.task_branch}; notes go on {environ.notes_branch}.",
            )


def _read_environ(hook: str) -> contract.Environ:
    """The session variables, or a refusal naming the missing ones: git shows hooks' stderr, not tracebacks."""
    try:
        return contract.read_environ()
    except contract.MissingVariables as error:
        sys.exit(f"{hook}: {error}")


def _staged_paths() -> list[str]:
    """Paths staged for the commit being made, as git spells them, whatever characters they hold."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRD", "-z"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [path for path in result.stdout.split("\0") if path]
