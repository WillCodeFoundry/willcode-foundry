"""agent_runtime.git_hooks, in-process: pre_push on the lines git passes it, and pre_commit and prepare_commit_msg
against real checkouts that session_setup made, each given the repository as a Git.

tests/sandbox_image/test_git_hooks.py runs each hook through its stub, by real commits and pushes.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from agent_runtime import contract, git_hooks
from agent_runtime.git import Git
from agent_runtime.task.lifecycles import FEATURE
from agent_runtime.task.state import TaskState
from foundry.task import NOTES_BRANCH, Task
from tests.support import TASK, git

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
    agent_task_notes_dir=".notes/t1",
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

    with pytest.raises(git_hooks.GitHookRefused) as refused:
        git_hooks.pre_push(refs, ENVIRON)

    assert str(refused.value) == (  # what was wrong, then what to do instead
        "pre-push: refusing\n\n"
        f"  You may only push task/t1 and notes, not {named}.\n"
        "  Code goes on task/t1; notes go on notes.\n"
    )


# --- against real checkouts --------------------------------------------------


Checkouts = tuple[contract.Environ, Path, Path]
OTHER_TASK = Task("T2")


def stage(cwd: Path, name: str) -> None:
    path = cwd / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{name}\n")
    git(cwd, "add", name)


def commit_unchecked(cwd: Path, message: str) -> None:
    """A commit the hooks don't see: another task's agent's, say, or setup for a case."""
    git(cwd, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", message)


def refusal_of(call: Callable[[], None]) -> str:
    with pytest.raises(git_hooks.GitHookRefused) as refused:
        call()
    return str(refused.value)


@pytest.mark.parametrize("path", [f"{TASK.task_notes_dir}/PROGRESS.md", f"src/{TASK.task_notes_dir}/PROGRESS.md"])
def test_notes_on_the_task_branch_are_refused_at_any_depth(checkouts: Checkouts, path: str) -> None:
    session, code, _ = checkouts
    stage(code, path)

    refusal = refusal_of(lambda: git_hooks.pre_commit(session, Git(code)))

    assert refusal.startswith("pre-commit: refusing\n\n")
    assert f"Task notes belong on {NOTES_BRANCH}" in refusal and f"    {path}" in refusal


@pytest.mark.parametrize("path", ["NOTES.md", "PROGRESS.md", "src/main.py"])
def test_code_files_are_accepted_on_the_task_branch(checkouts: Checkouts, path: str) -> None:
    session, code, _ = checkouts
    stage(code, path)

    git_hooks.pre_commit(session, Git(code))


@pytest.mark.parametrize("path", [f"{TASK.task_notes_dir}/PROGRESS.md", TASK.task_file])
def test_this_tasks_notes_are_accepted_on_the_notes_branch(checkouts: Checkouts, path: str) -> None:
    session, _, notes = checkouts
    stage(notes, path)

    git_hooks.pre_commit(session, Git(notes))


def test_another_tasks_folder_is_refused(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    stage(notes, f"{OTHER_TASK.task_notes_dir}/PROGRESS.md")

    assert f"only change files in {TASK.task_notes_dir}/" in refusal_of(
        lambda: git_hooks.pre_commit(session, Git(notes))
    )


def test_moving_another_tasks_file_into_own_folder_is_refused(checkouts: Checkouts) -> None:
    """A rename stages a deletion in the other task's folder; git's rename detection would list only the new
    path, inside this task's folder."""
    session, _, notes = checkouts
    theirs = f"{OTHER_TASK.task_notes_dir}/PROGRESS.md"
    stage(notes, theirs)
    commit_unchecked(notes, f"{OTHER_TASK.id}: progress")
    git(notes, "mv", theirs, f"{TASK.task_notes_dir}/x.md")

    assert f"    {theirs}" in refusal_of(lambda: git_hooks.pre_commit(session, Git(notes)))


def test_replacing_another_tasks_file_with_a_link_is_refused(checkouts: Checkouts) -> None:
    """A type change: the file in the other task's folder becomes a link, its content gone."""
    session, _, notes = checkouts
    theirs = f"{OTHER_TASK.task_notes_dir}/PROGRESS.md"
    stage(notes, theirs)
    commit_unchecked(notes, f"{OTHER_TASK.id}: progress")
    (notes / theirs).unlink()
    (notes / theirs).symlink_to("elsewhere")
    git(notes, "add", theirs)

    assert f"    {theirs}" in refusal_of(lambda: git_hooks.pre_commit(session, Git(notes)))


def test_a_commit_on_another_branch_is_left_alone(checkouts: Checkouts) -> None:
    """It can't be pushed: pre-push refuses it."""
    session, code, _ = checkouts
    git(code, "switch", "-q", "-c", "scratch")
    stage(code, f"{TASK.task_notes_dir}/PROGRESS.md")

    git_hooks.pre_commit(session, Git(code))


def message_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(text)
    return path


def test_the_task_trailer_is_added_once(checkouts: Checkouts, tmp_path: Path) -> None:
    session, code, _ = checkouts
    message = message_file(tmp_path, "feat: hello\n\nWhy.\n")

    git_hooks.prepare_commit_msg([str(message)], session, Git(code))
    git_hooks.prepare_commit_msg([str(message)], session, Git(code))

    assert message.read_text() == f"feat: hello\n\nWhy.\n\nTask: {TASK.id}\n"


@pytest.mark.parametrize("text", ["", "# only a comment\n"])
def test_an_empty_message_gets_no_trailer_so_git_still_aborts(checkouts: Checkouts, tmp_path: Path, text: str) -> None:
    session, code, _ = checkouts
    message = message_file(tmp_path, text)

    git_hooks.prepare_commit_msg([str(message)], session, Git(code))

    assert message.read_text() == text


def test_no_trailer_off_the_task_branch(checkouts: Checkouts, tmp_path: Path) -> None:
    session, _, notes = checkouts
    message = message_file(tmp_path, f"{TASK.id}: progress\n")

    git_hooks.prepare_commit_msg([str(message)], session, Git(notes))

    assert message.read_text() == f"{TASK.id}: progress\n"


def test_prepare_commit_msg_without_its_file_is_refused(checkouts: Checkouts) -> None:
    session, code, _ = checkouts

    assert refusal_of(lambda: git_hooks.prepare_commit_msg([], session, Git(code))) == (
        "prepare-commit-msg: refusing: git passed no message file"
    )


# --- STATE.json, judged by pre-push -------------------------------------------

STATE_PATH = f"{TASK.task_notes_dir}/STATE.json"
IMPLEMENT = TaskState(lifecycle=FEATURE, state="implement", previous="plan", note="Approved.")
REVIEW = IMPLEMENT.after("submit", "Ready for review.")


def commit_state(notes: Path, task_state: TaskState, *also: str) -> None:
    """A commit of STATE.json, and of ``also``, that no hook sees, as any git command could make it."""
    (notes / STATE_PATH).write_text(task_state.to_json())
    git(notes, "add", STATE_PATH)
    for name in also:
        stage(notes, name)
    commit_unchecked(notes, f"state: {task_state.state}")


def pushed(notes: Path) -> None:
    """What is on the notes checkout, pushed past the hooks: foundry's or an earlier turn's."""
    git(notes, "-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "HEAD")


def push_check(session: contract.Environ, notes: Path) -> None:
    """pre_push on the line git passes for pushing the notes checkout's HEAD to origin's notes branch."""
    ref = f"refs/heads/{session.agent_notes_branch}"
    local = git(notes, "rev-parse", "HEAD").stdout.strip()
    remote = git(notes, "rev-parse", f"origin/{session.agent_notes_branch}").stdout.strip()
    git_hooks.pre_push([f"{ref} {local} {ref} {remote}\n"], session, Git(notes))


def test_a_legal_transition_is_accepted_however_it_was_committed(checkouts: Checkouts) -> None:
    """The content decides: not who wrote it, nor whether it came with other notes."""
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)
    pushed(notes)
    commit_state(notes, REVIEW, f"{TASK.task_notes_dir}/PROGRESS.md")

    push_check(session, notes)


def test_a_push_that_leaves_the_task_state_as_it_was_is_accepted(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)
    pushed(notes)
    commit_state(notes, REVIEW)
    git(notes, "-c", "core.hooksPath=/dev/null", "revert", "--no-edit", "HEAD")

    push_check(session, notes)


@pytest.mark.parametrize(
    ("before", "after", "reason"),
    [
        (IMPLEMENT, REVIEW.after("approve", "LGTM"), "implement can't go to deliver"),
        (
            IMPLEMENT,
            TaskState(lifecycle=FEATURE, state="done", previous="implement", note="x"),
            "implement can't go to done",
        ),
        (
            IMPLEMENT,
            TaskState(lifecycle=FEATURE, state="review", previous="plan", note="x"),
            "previous must be implement",
        ),
        (REVIEW, IMPLEMENT, "it is the reviewer's turn, not the dev's"),
    ],
    ids=["two turns in one push", "cherry-picked or merged", "wrong previous", "a pushed turn reverted"],
)
def test_an_illegal_change_is_refused_saying_why_and_how_to_undo_it(
    checkouts: Checkouts, before: TaskState, after: TaskState, reason: str
) -> None:
    session, _, notes = checkouts
    commit_state(notes, before)
    pushed(notes)
    commit_state(notes, after)

    refusal = refusal_of(lambda: push_check(session, notes))

    assert f"{STATE_PATH}: not a transition the dev may make: {reason}" in refusal
    assert f"git checkout origin/{session.agent_notes_branch} -- {STATE_PATH}" in refusal


def test_creating_the_task_state_is_refused(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)

    assert "it can't be created in the sandbox" in refusal_of(lambda: push_check(session, notes))


def test_deleting_the_task_state_is_refused(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)
    pushed(notes)
    git(notes, "rm", "-q", STATE_PATH)
    commit_unchecked(notes, "drop state")

    assert "it can't be deleted in the sandbox" in refusal_of(lambda: push_check(session, notes))


def test_a_file_that_isnt_a_task_state_is_refused(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)
    pushed(notes)
    (notes / STATE_PATH).write_text("{}")
    git(notes, "add", STATE_PATH)
    commit_unchecked(notes, "bad state")

    assert "is not a task state" in refusal_of(lambda: push_check(session, notes))


def test_pre_commit_no_longer_judges_the_task_state(checkouts: Checkouts) -> None:
    """One guard: pre-push. A commit pre-push would refuse still commits, and is refused when pushed."""
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)
    (notes / STATE_PATH).write_text(IMPLEMENT.moved("done", "x").to_json())
    git(notes, "add", STATE_PATH)

    git_hooks.pre_commit(session, Git(notes))
