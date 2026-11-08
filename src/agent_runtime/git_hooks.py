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


def pre_commit(variables: contract.SessionVariables | None = None, git: Git | None = None) -> None:
    """Refuse a commit that puts files where they don't belong.

    task branch: no task notes: nothing under the notes root, at any depth, so notes written from a
                 subfolder are caught too;
    notes branch: only this task's notes dir, and LOG_FILE there only added to, as below.
    Commits on any other branch are left alone: they can't be pushed.
    """
    variables = variables or _read_variables("pre-commit")
    git = git or Git()
    branch = git.current_branch()
    if branch == variables.agent_task_branch:
        refused_paths = [path for path in _staged_paths(git) if _is_under(variables.agent_notes_root, path)]
        rule = (
            f"Task notes belong on {variables.agent_notes_branch}, "
            f"in $AGENT_NOTES_CHECKOUT_DIR/{variables.agent_task_notes_dir}/, not on {variables.agent_task_branch}:"
        )
    elif branch == variables.agent_notes_branch:
        refused_paths = [
            path for path in _staged_paths(git) if not path.startswith(f"{variables.agent_task_notes_dir}/")
        ]
        rule = f"On {variables.agent_notes_branch} you may only change files in {variables.agent_task_notes_dir}/:"
    else:
        return
    if refused_paths:
        raise _refusal(
            "pre-commit",
            rule,
            *(f"    {path}" for path in refused_paths),
            "",
            "Unstage with: git restore --staged <file>",
        )
    if branch == variables.agent_notes_branch:
        _require_log_only_added_to(variables, git)


def _require_log_only_added_to(variables: contract.SessionVariables, git: Git) -> None:
    """Refuse a staged LOG_FILE that changes what origin has: entries may only be added after it.

    Entries not yet pushed may still change, so amending your own last commit works. A guardrail: it trusts
    origin's ref as last fetched, and a role set on it could change the file through another commit.
    """
    path = f"{variables.agent_task_notes_dir}/{LOG_FILE}"
    if path not in _staged_paths(git):
        return
    pushed = _text_at(git, f"refs/remotes/origin/{variables.agent_notes_branch}:{path}") or ""
    staged = _text_at(git, f":{path}")
    if staged is None or not staged.startswith(pushed):
        raise _refusal(
            "pre-commit",
            f"{LOG_FILE} only grows: the entries already pushed can't change or go.",
            "Put them back as they were, add yours after them, and correct an entry by appending another.",
            f"See what changed with: git diff origin/{variables.agent_notes_branch} -- {path}",
        )


def _text_at(git: Git, revision_and_path: str) -> str | None:
    """A file's text at ``<revision>:<path>``, or in the index at ``:<path>``; None when it isn't there."""
    result = git.run_captured("show", revision_and_path)
    return result.stdout if result.returncode == 0 else None


def prepare_commit_msg(
    args: Sequence[str] | None = None, variables: contract.SessionVariables | None = None, git: Git | None = None
) -> None:
    """Add a "Task: <task>" trailer to every commit on the task branch, so each code commit traces back to
    its task without the agent having to remember. Runs even with --no-verify. git passes the message
    file first."""
    variables = variables or _read_variables("prepare-commit-msg")
    git = git or Git()
    hook_args = sys.argv[1:] if args is None else args
    if git.current_branch() != variables.agent_task_branch:
        return
    if not hook_args:
        raise GitHookRefused("prepare-commit-msg: refusing: git passed no message file")
    message_file = hook_args[0]
    # An empty message aborts the commit; a trailer would make it go through.
    if not git.output("stripspace", "--strip-comments", input=Path(message_file).read_text()):
        return
    trailer = f"Task: {variables.agent_task_id}"
    git.output("interpret-trailers", "--in-place", "--if-exists", "doNothing", "--trailer", trailer, message_file)


def pre_push(ref_lines: Iterable[str] | None = None, variables: contract.SessionVariables | None = None) -> None:
    """Refuse a push to anything but this task's branch and the notes branch.

    The project's GitHub rulesets allow any task branch, since GitHub can't tell one task from another;
    this keeps a role to its own. git passes one line per ref on stdin:
    ``<local ref> <local sha> <remote ref> <remote sha>``.
    """
    variables = variables or _read_variables("pre-push")
    allowed = {f"refs/heads/{variables.agent_task_branch}", f"refs/heads/{variables.agent_notes_branch}"}
    for line in sys.stdin if ref_lines is None else ref_lines:
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
                f"You may only push {variables.agent_task_branch} and {variables.agent_notes_branch}, "
                f"not {remote_ref.removeprefix('refs/heads/')}.",
                f"Code goes on {variables.agent_task_branch}; notes go on {variables.agent_notes_branch}.",
            )


def _refusal(hook: str, *lines: str) -> GitHookRefused:
    """Every refusal's shape: the hook, what was wrong, then what to do instead."""
    body = "".join(f"  {line}\n" for line in lines)
    return GitHookRefused(f"{hook}: refusing\n\n{body}")


def _read_variables(hook: str) -> contract.SessionVariables:
    """The session variables, or a refusal naming the missing ones."""
    try:
        return contract.read_session_variables()
    except contract.MissingVariables as error:
        raise GitHookRefused(f"{hook}: {error}") from None


def _is_under(root: str, path: str) -> bool:
    """Whether ``path`` sits in a dir named ``root``, at any depth."""
    root_parts, dir_parts = PurePosixPath(root).parts, PurePosixPath(path).parts[:-1]
    return any(dir_parts[i : i + len(root_parts)] == root_parts for i in range(len(dir_parts)))


def _staged_paths(git: Git) -> list[str]:
    """Paths staged for the commit being made, as git spells them, whatever characters they hold. Every kind of
    change counts, a type change included, and a rename is listed as both its paths."""
    staged = git.output("diff", "--cached", "--name-only", "--no-renames", "-z")
    return [path for path in staged.split("\0") if path]
