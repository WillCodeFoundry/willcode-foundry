"""agent_runtime.git_hooks, without git where they need none.

The hooks that read the repository are tested end to end, in tests/agent_kit/test_git_hooks.py.
"""

from pathlib import Path

import pytest

from agent_runtime import contract, git_hooks

ENVIRON = contract.Environ(
    agent_role="dev",
    agent_task="t1",
    agent_kit_dir=Path("/kit"),
    agent_repo_url="git@github.com:o/p.git",
    agent_project_dir=Path("/work/p"),
    agent_notes_dir=Path("/work/p-notes"),
    agent_task_branch="task/t1",
    agent_notes_branch="notes",
    agent_notes_root=".notes",
    agent_task_notes=".notes/t1",
    agent_task_file=".notes/t1/TASK.md",
)
ZERO = "0" * 40


OLD, NEW = "a" * 40, "b" * 40


@pytest.mark.parametrize(
    ("local_sha", "remote_sha"),
    [(NEW, OLD), (NEW, ZERO), (ZERO, OLD)],
    ids=["update", "new branch", "deletion, which the rulesets refuse"],
)
def test_pushing_the_task_and_notes_branches_is_accepted(local_sha: str, remote_sha: str) -> None:
    """git's lines: <local ref> <local sha> <remote ref> <remote sha>; an all-zero local sha means delete."""
    refs = [
        f"refs/heads/task/t1 {local_sha} refs/heads/task/t1 {remote_sha}\n",
        f"refs/heads/notes {local_sha} refs/heads/notes {remote_sha}\n",
    ]
    git_hooks.pre_push(refs, ENVIRON)


@pytest.mark.parametrize(("remote_ref", "named"), [("refs/heads/task/t2", "task/t2"), ("refs/tags/v1", "refs/tags/v1")])
def test_pushing_anything_else_is_refused(remote_ref: str, named: str) -> None:
    refs = [f"refs/heads/task/t1 {OLD} refs/heads/task/t1 {NEW}\n", f"HEAD {OLD} {remote_ref} {NEW}\n"]

    with pytest.raises(git_hooks.Refused) as refused:
        git_hooks.pre_push(refs, ENVIRON)

    assert str(refused.value) == (  # what was wrong, then what to do instead
        "pre-push: refusing\n\n"
        f"  You may only push task/t1 and notes, not {named}.\n"
        "  Code goes on task/t1; notes go on notes.\n"
    )
