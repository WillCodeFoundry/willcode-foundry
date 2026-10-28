"""The git hooks, which core.hooksPath runs from the kit's hooks/ stubs; git runs them at the checkout's root.

- ``pre_commit``: what each checkout may commit, so tasks don't step on each other.
- ``prepare_commit_msg``: the ``Task:`` trailer on every commit on the task branch.
- ``pre_push``: pushes only to this task's branch and the notes branch, and a change to STATE.json only as a legal
  transition for this role.

Each takes what git passes, the session variables and the repository, defaulting to this process's and the
current directory's, and raises GitHookRefused, whose message says what was wrong and what to do instead.
"""

import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

from agent_runtime import contract
from agent_runtime.git import Git
from agent_runtime.task.state import STATE_FILE, TaskState, TaskStateRefused, legal_change

_ZERO = "0" * 40
"""The sha git passes for a ref that doesn't exist on one side of a push."""


class GitHookRefused(Exception):
    """A hook refuses: the message is the whole refusal, as the agent will read it."""


def pre_commit(session: contract.Environ | None = None, git: Git | None = None) -> None:
    """Refuse a commit that puts files where they don't belong.

    task branch: no task notes: nothing under the notes root, at any depth, so notes written from a
                 subfolder are caught too;
    notes branch: only this task's notes dir. pre_push judges a change to STATE.json.
    Commits on any other branch are left alone: they can't be pushed.
    """
    session = session or _read_session("pre-commit")
    git = git or Git()
    branch = git.current_branch()
    if branch == session.agent_task_branch:
        refused = [path for path in _staged_paths(git) if _is_under(session.agent_notes_root, path)]
        rule = (
            f"Task notes belong on {session.agent_notes_branch}, in $AGENT_NOTES_DIR/{session.agent_task_notes_dir}/, "
            f"not on {session.agent_task_branch}:"
        )
    elif branch == session.agent_notes_branch:
        staged = _staged_paths(git)
        refused = [path for path in staged if not path.startswith(f"{session.agent_task_notes_dir}/")]
        rule = f"On {session.agent_notes_branch} you may only change files in {session.agent_task_notes_dir}/:"
    else:
        return
    if refused:
        raise _refusal(
            "pre-commit", rule, *(f"    {path}" for path in refused), "", "Unstage with: git restore --staged <file>"
        )


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
    """Refuse a push to anything but this task's branch and the notes branch, and a push to the notes branch
    that changes STATE.json other than by a legal transition for this role.

    The project's GitHub rulesets allow any task branch, since GitHub can't tell one task from another;
    this keeps a role to its own. git passes one line per ref on stdin:
    ``<local ref> <local sha> <remote ref> <remote sha>``.
    """
    session = session or _read_session("pre-push")
    git = git or Git()
    notes_ref = f"refs/heads/{session.agent_notes_branch}"
    allowed = {f"refs/heads/{session.agent_task_branch}", notes_ref}
    for line in sys.stdin if refs is None else refs:
        match line.split():
            case []:
                continue
            case [_local_ref, local_sha, remote_ref, remote_sha]:
                pass
            case _:
                local_sha = remote_ref = remote_sha = ""
        if remote_ref not in allowed:
            raise _refusal(
                "pre-push",
                f"You may only push {session.agent_task_branch} and {session.agent_notes_branch}, "
                f"not {remote_ref.removeprefix('refs/heads/')}.",
                f"Code goes on {session.agent_task_branch}; notes go on {session.agent_notes_branch}.",
            )
        if remote_ref == notes_ref:
            _check_task_state(session, git, local_sha, remote_sha)


def _check_task_state(session: contract.Environ, git: Git, local_sha: str, remote_sha: str) -> None:
    """Refuse a push that leaves STATE.json other than as a legal transition, for this role, from origin's.

    Only the states before and after the push are judged. So every git command that makes commits is judged
    alike, and who made the change doesn't matter. A deletion, a new branch, or a remote commit this checkout
    hasn't fetched is left to the rulesets, which refuse it as a deletion or a push that isn't a fast-forward.
    """
    if local_sha == _ZERO or not git.succeeds("cat-file", "-e", f"{remote_sha}^{{commit}}"):
        return
    path = f"{session.agent_task_notes_dir}/{STATE_FILE}"
    if git.succeeds("diff", "--quiet", remote_sha, local_sha, "--", path):
        return
    undo = (
        "",
        "Put it back as origin has it, then commit and push again:",
        f"    git checkout origin/{session.agent_notes_branch} -- {path}",
        'End your turn with: "$AGENT_KIT_DIR/bin/task" <event> "<hand-off note>"',
    )
    try:
        old, new = _task_state(git, remote_sha, path, "created"), _task_state(git, local_sha, path, "deleted")
    except TaskStateRefused as error:
        raise _refusal("pre-push", f"{path} can't change this way: {error}", *undo) from None
    if reason := legal_change(old, new, session.agent_role):
        raise _refusal("pre-push", f"{path}: not a transition the {session.agent_role} may make: {reason}.", *undo)


def _task_state(git: Git, revision: str, path: str, missing: str) -> TaskState:
    """The task state at ``revision``; TaskStateRefused saying it can't be ``missing`` when the file isn't there."""
    where = f"{revision}:{path}"
    if not git.succeeds("cat-file", "-e", where):
        raise TaskStateRefused(f"it can't be {missing} in the sandbox")
    return TaskState.parse(git.output("show", where), where)


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


def _staged_paths(git: Git) -> list[str]:
    """Paths staged for the commit being made, as git spells them, whatever characters they hold. Every kind of
    change counts, a type change included, and a rename is listed as both its paths."""
    staged = git.output("diff", "--cached", "--name-only", "--no-renames", "-z")
    return [path for path in staged.split("\0") if path]
