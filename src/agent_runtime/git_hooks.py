"""The git hooks, which core.hooksPath runs from the kit's hooks/ stubs; git runs them at the checkout's root.

- ``pre_commit``: what each checkout may commit, so tasks don't step on each other.
- ``prepare_commit_msg``: the ``Task:`` trailer on every commit on the task branch.
- ``pre_push``: pushes only to this task's branch and the notes branch.

Each takes what git passes, and the session variables, defaulting to this process's. Every refusal has the
same shape (``_refuse``): what was wrong, then what to do instead.
"""

import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import NoReturn

from agent_runtime import contract
from agent_runtime.git import Git


def pre_commit(env: contract.Environ | None = None) -> None:
    """Refuse a commit that puts files where they don't belong.

    task branch: no task notes: nothing under the notes root, at any depth, so notes written from a
                 subfolder are caught too;
    notes branch: only this task's notes folder.
    Commits on any other branch are left alone: they can't be pushed.
    """
    environ = env or _read_environ("pre-commit")
    branch = Git().current_branch()
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
        _refuse(
            "pre-commit", rule, *(f"    {path}" for path in refused), "", "Unstage with: git restore --staged <file>"
        )


def prepare_commit_msg(args: Sequence[str] | None = None, env: contract.Environ | None = None) -> None:
    """Add a "Task: <task>" trailer to every commit on the task branch, so each code commit traces back to
    its task without the agent having to remember. Runs even with --no-verify. git passes the message
    file first."""
    environ = env or _read_environ("prepare-commit-msg")
    arguments = sys.argv[1:] if args is None else args
    if Git().current_branch() != environ.task_branch:
        return
    if not arguments:
        sys.exit("prepare-commit-msg needs the message file")
    message_file = arguments[0]
    # An empty message aborts the commit; a trailer would make it go through.
    if not Git().output("stripspace", "--strip-comments", input=Path(message_file).read_text()):
        return
    trailer = f"Task: {environ.task}"
    Git().output("interpret-trailers", "--in-place", "--if-exists", "doNothing", "--trailer", trailer, message_file)


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
            _refuse(
                "pre-push",
                f"You may only push {environ.task_branch} and {environ.notes_branch}, "
                f"not {remote_ref.removeprefix('refs/heads/')}.",
                f"Code goes on {environ.task_branch}; notes go on {environ.notes_branch}.",
            )


def _refuse(hook: str, *lines: str) -> NoReturn:
    """Print a refusal that says what was wrong and what to do instead, then exit non-zero."""
    body = "".join(f"  {line}\n" for line in lines)
    sys.stderr.write(f"{hook}: refusing\n\n{body}\n")
    sys.exit(1)


def _read_environ(hook: str) -> contract.Environ:
    """The session variables, or a refusal naming the missing ones: git shows hooks' stderr, not tracebacks."""
    try:
        return contract.read_environ()
    except contract.MissingVariables as error:
        sys.exit(f"{hook}: {error}")


def _staged_paths() -> list[str]:
    """Paths staged for the commit being made, as git spells them, whatever characters they hold. A rename is
    listed as both its paths: a move out of another task's folder deletes a file there."""
    staged = Git().output("diff", "--cached", "--name-only", "--no-renames", "--diff-filter=ACMD", "-z")
    return [path for path in staged.split("\0") if path]
