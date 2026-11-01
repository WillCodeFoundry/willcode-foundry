"""The git hooks, which core.hooksPath runs from the kit's hooks/ stubs; git runs them at the checkout's root.

- ``pre_commit``: what each checkout may commit, so tasks don't step on each other, and the task's LOG_FILE
  only grows.
- ``prepare_commit_msg``: the ``Task:`` trailer on every commit on the task branch.
- ``pre_push``: pushes only to this task's branch and the notes branch.

Each takes what git passes, the session variables and the repository, defaulting to this process's and the
current directory's, and raises GitHookRefused, whose message says what was wrong and what to do instead.
"""

import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Final

from agent_runtime import contract
from agent_runtime.git import Git

LOG_FILE: Final = "LOG.md"
"""The task notes file every role appends to, as agent-kit/AGENTS.md says; config/task-template/ starts it."""


class GitHookRefused(Exception):
    """A hook refuses: the message is the whole refusal, as the agent will read it."""


def pre_commit(session: contract.Environ | None = None, git: Git | None = None) -> None:
    """Refuse a commit that puts files where they don't belong.

    task branch: no task notes: nothing under the notes root, at any depth, so notes written from a
                 subfolder are caught too;
    notes branch: only this task's notes dir, and LOG_FILE there only added to, as below.
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
        refused = [path for path in _staged_paths(git) if not path.startswith(f"{session.agent_task_notes_dir}/")]
        rule = f"On {session.agent_notes_branch} you may only change files in {session.agent_task_notes_dir}/:"
    else:
        return
    if refused:
        raise _refusal(
            "pre-commit", rule, *(f"    {path}" for path in refused), "", "Unstage with: git restore --staged <file>"
        )
    if branch == session.agent_notes_branch:
        _require_log_only_added_to(session, git)


def _require_log_only_added_to(session: contract.Environ, git: Git) -> None:
    """Refuse a staged LOG_FILE that changes what origin has: entries may only be added after it.

    Entries not yet pushed may still change, so amending your own last commit works. A guardrail: it trusts
    origin's ref as last fetched, and a role set on it could change the file through another commit.
    """
    path = f"{session.agent_task_notes_dir}/{LOG_FILE}"
    if path not in _staged_paths(git):
        return
    pushed = _file_at(git, f"refs/remotes/origin/{session.agent_notes_branch}:{path}") or ""
    staged = _file_at(git, f":{path}")
    if staged is None or not staged.startswith(pushed):
        raise _refusal(
            "pre-commit",
            f"{LOG_FILE} only grows: the entries already pushed can't change or go.",
            "Put them back as they were, add yours after them, and correct an entry by appending another.",
            f"See what changed with: git diff origin/{session.agent_notes_branch} -- {path}",
        )


def _file_at(git: Git, revision_and_path: str) -> str | None:
    """A file's text at ``<revision>:<path>``, or in the index at ``:<path>``; None when it isn't there."""
    result = git.run_captured("show", revision_and_path)
    return result.stdout if result.returncode == 0 else None


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


def pre_push(refs: Iterable[str] | None = None, session: contract.Environ | None = None) -> None:
    """Refuse a push to anything but this task's branch and the notes branch.

    The project's GitHub rulesets allow any task branch, since GitHub can't tell one task from another;
    this keeps a role to its own. git passes one line per ref on stdin:
    ``<local ref> <local sha> <remote ref> <remote sha>``.
    """
    session = session or _read_session("pre-push")
    allowed = {f"refs/heads/{session.agent_task_branch}", f"refs/heads/{session.agent_notes_branch}"}
    for line in sys.stdin if refs is None else refs:
        match line.split():
            case []:
                continue
            case [_local_ref, _local_sha, remote_ref, *_]:
                pass
            case _:
                remote_ref = ""
        if remote_ref not in allowed:
            raise _refusal(
                "pre-push",
                f"You may only push {session.agent_task_branch} and {session.agent_notes_branch}, "
                f"not {remote_ref.removeprefix('refs/heads/')}.",
                f"Code goes on {session.agent_task_branch}; notes go on {session.agent_notes_branch}.",
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


def _staged_paths(git: Git) -> list[str]:
    """Paths staged for the commit being made, as git spells them, whatever characters they hold. Every kind of
    change counts, a type change included, and a rename is listed as both its paths."""
    staged = git.output("diff", "--cached", "--name-only", "--no-renames", "-z")
    return [path for path in staged.split("\0") if path]
