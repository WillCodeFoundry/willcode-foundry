"""agent_runtime.git_hooks and refusal, without git where they need none.

The hooks that read the repository are tested end to end, in tests/agent_kit/test_git_hooks.py.
"""

from pathlib import Path

import pytest

from agent_runtime import contract, git_hooks
from agent_runtime.refusal import refuse

ENVIRON = contract.Environ(
    role="dev",
    task="t1",
    kit_dir=Path("/kit"),
    repo_url="git@github.com:o/p.git",
    project_dir=Path("/work/p"),
    notes_dir=Path("/work/p-notes"),
    task_branch="task/t1",
    notes_branch="notes",
    notes_root=".notes",
    task_notes=".notes/t1",
    task_file=".notes/t1/TASK.md",
)
ZERO = "0" * 40


def test_a_refusal_says_what_was_wrong_then_what_to_do(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        refuse("pre-push", "What was wrong.", "", "What to do.")

    assert exited.value.code == 1
    assert capsys.readouterr().err == "pre-push: refusing\n\n  What was wrong.\n  \n  What to do.\n\n"


def test_pushing_the_task_and_notes_branches_is_accepted() -> None:
    refs = [f"refs/heads/x {ZERO} refs/heads/task/t1 {ZERO}\n", f"refs/heads/notes {ZERO} refs/heads/notes {ZERO}\n"]
    git_hooks.pre_push(refs, ENVIRON)


@pytest.mark.parametrize(("remote_ref", "named"), [("refs/heads/task/t2", "task/t2"), ("refs/tags/v1", "refs/tags/v1")])
def test_pushing_anything_else_is_refused(capsys: pytest.CaptureFixture[str], remote_ref: str, named: str) -> None:
    refs = [f"refs/heads/task/t1 {ZERO} refs/heads/task/t1 {ZERO}\n", f"HEAD {ZERO} {remote_ref} {ZERO}\n"]

    with pytest.raises(SystemExit):
        git_hooks.pre_push(refs, ENVIRON)

    assert f"You may only push task/t1 and notes, not {named}." in capsys.readouterr().err
