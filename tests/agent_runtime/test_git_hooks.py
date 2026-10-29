"""agent_runtime.git_hooks, in-process: pre_push on the lines git passes it, then pre_push and prepare_commit_msg
against real checkouts that session_setup made, each given the repository as a Git.

tests/sandbox_image/test_git_hooks.py runs each hook through its stub, by real commits and pushes.
"""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from agent_runtime import contract, git_hooks
from agent_runtime.git import Git
from agent_runtime.task.lifecycles import BUGFIX, FEATURE
from agent_runtime.task.state import TaskState, state_path
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
        "  Code goes on task/t1. Notes go on notes.\n"
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


def push_check(session: contract.Environ, checkout: Path, branch: str | None = None) -> None:
    """pre_push on the line git passes for pushing ``checkout``'s HEAD to ``branch`` on origin: the notes branch by
    default."""
    branch = branch or session.agent_notes_branch
    ref = f"refs/heads/{branch}"
    local = git(checkout, "rev-parse", "HEAD").stdout.strip()
    remote = git(checkout, "rev-parse", f"origin/{branch}").stdout.strip()
    git_hooks.pre_push([f"HEAD {local} {ref} {remote}\n"], session, Git(checkout))


def committed(checkout: Path, *paths: str) -> None:
    """``paths`` committed on ``checkout``, as any git command could commit them."""
    for path in paths:
        stage(checkout, path)
    commit_unchecked(checkout, "change")


@pytest.mark.parametrize("path", [f"{TASK.task_notes_dir}/PROGRESS.md", f"src/{TASK.task_notes_dir}/PROGRESS.md"])
def test_notes_on_the_task_branch_are_refused_at_any_depth(checkouts: Checkouts, path: str) -> None:
    session, code, _ = checkouts
    committed(code, path)

    refusal = refusal_of(lambda: push_check(session, code, session.agent_task_branch))

    assert refusal.startswith("pre-push: refusing\n\n")
    assert f"Task notes belong on {NOTES_BRANCH}" in refusal and f"    {path}" in refusal
    origin_sha = git(code, "rev-parse", f"origin/{session.agent_task_branch}").stdout.strip()
    assert f'git -C "$AGENT_PROJECT_DIR" reset --soft {origin_sha}' in refusal
    assert f'git -C "$AGENT_PROJECT_DIR" restore --source={origin_sha} --staged --worktree -- {path}' in refusal


@pytest.mark.parametrize("path", ["NOTES.md", "PROGRESS.md", "src/main.py"])
def test_code_files_are_accepted_on_the_task_branch(checkouts: Checkouts, path: str) -> None:
    session, code, _ = checkouts
    committed(code, path)

    push_check(session, code, session.agent_task_branch)


@pytest.mark.parametrize("path", [f"{TASK.task_notes_dir}/PROGRESS.md", TASK.task_file])
def test_this_tasks_notes_are_accepted_on_the_notes_branch(checkouts: Checkouts, path: str) -> None:
    session, _, notes = checkouts
    committed(notes, path)

    push_check(session, notes)


def test_another_tasks_folder_is_refused(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    committed(notes, f"{OTHER_TASK.task_notes_dir}/PROGRESS.md")

    assert f"only change files in {TASK.task_notes_dir}/" in refusal_of(lambda: push_check(session, notes))


def test_another_tasks_state_committed_on_a_detached_head_is_refused(checkouts: Checkouts) -> None:
    """Round 2's R32: no commit hook runs on a detached HEAD, and the push names the notes branch only remotely."""
    session, _, notes = checkouts
    theirs = state_path(OTHER_TASK.task_notes_dir)
    committed(notes, theirs)
    pushed(notes)
    git(notes, "switch", "-q", "--detach")
    (notes / theirs).write_text("changed\n")
    git(notes, "add", theirs)
    commit_unchecked(notes, "move their task")

    assert f"    {theirs}" in refusal_of(lambda: push_check(session, notes))


def test_reverting_another_tasks_notes_is_refused(checkouts: Checkouts) -> None:
    """A revert deletes what the reverted commit added, in the other task's folder."""
    session, _, notes = checkouts
    theirs = f"{OTHER_TASK.task_notes_dir}/PROGRESS.md"
    committed(notes, theirs)
    pushed(notes)
    git(notes, "-c", "core.hooksPath=/dev/null", "revert", "--no-edit", "HEAD")

    assert f"    {theirs}" in refusal_of(lambda: push_check(session, notes))


def test_following_the_refusals_advice_makes_the_push_pass(checkouts: Checkouts) -> None:
    """The refusal's own commands put back what didn't belong: a change, a deletion and a new file alike. They
    name their checkout, so they work run from a subfolder of the other checkout too."""
    session, code, notes = checkouts
    changed, deleted, added = (f"{OTHER_TASK.task_notes_dir}/{name}.md" for name in ("changed", "deleted", "added"))
    committed(notes, changed, deleted)
    pushed(notes)
    (notes / changed).write_text("theirs, changed\n")
    git(notes, "add", changed)
    git(notes, "rm", "-q", deleted)
    committed(notes, added, f"{TASK.task_notes_dir}/PROGRESS.md")
    advice = refusal_of(lambda: push_check(session, notes)).splitlines()
    commands = [line.strip() for line in advice if line.strip().startswith("git -C")]
    elsewhere = code / "src"
    elsewhere.mkdir(exist_ok=True)

    environ = {**os.environ, "AGENT_NOTES_DIR": str(notes)}
    for command in commands:
        subprocess.run(["sh", "-c", command], cwd=elsewhere, env=environ, check=True, capture_output=True)
    commit_unchecked(notes, "progress")

    push_check(session, notes)
    assert git(notes, "diff", "--name-only", f"origin/{session.agent_notes_branch}", "HEAD").stdout.split() == [
        f"{TASK.task_notes_dir}/PROGRESS.md"
    ]
    assert git(code, "status", "--porcelain").stdout == ""


def test_the_advice_still_works_after_origin_moves(checkouts: Checkouts, tmp_path: Path) -> None:
    """Round 4's R50: another task pushes after the refusal, and this checkout fetches it. The advice resets to
    the commit the push was judged against, so it doesn't undo the other task's change."""
    session, _, notes = checkouts
    committed(notes, f"{OTHER_TASK.task_notes_dir}/OOPS.md", f"{TASK.task_notes_dir}/PROGRESS.md")
    advice = refusal_of(lambda: push_check(session, notes)).splitlines()
    other = tmp_path / "other-role"
    url = git(notes, "remote", "get-url", "origin").stdout.strip()
    git(tmp_path, "clone", "-q", "-b", session.agent_notes_branch, url, str(other))
    committed(other, f"{OTHER_TASK.task_notes_dir}/THEIRS.md")
    pushed(other)
    git(notes, "fetch", "-q", "origin")

    for command in (line.strip() for line in advice if line.strip().startswith("git -C")):
        environ = {**os.environ, "AGENT_NOTES_DIR": str(notes)}
        subprocess.run(["sh", "-c", command], cwd=notes, env=environ, check=True, capture_output=True)
    commit_unchecked(notes, "progress")
    git(notes, "-c", "core.hooksPath=/dev/null", "pull", "-q", "--rebase", "origin", session.agent_notes_branch)

    push_check(session, notes)
    assert (notes / OTHER_TASK.task_notes_dir / "THEIRS.md").exists()


def test_notes_added_and_removed_within_one_push_are_refused(checkouts: Checkouts) -> None:
    """Round 3's R44: the push leaves no notes, but its commits carry them into the task branch's history."""
    session, code, _ = checkouts
    path = f"{TASK.task_notes_dir}/P.md"
    committed(code, path)
    git(code, "rm", "-q", path)
    commit_unchecked(code, "remove it again")

    assert f"    {path}" in refusal_of(lambda: push_check(session, code, session.agent_task_branch))


def test_the_advice_for_notes_added_and_removed_within_one_push_makes_it_pass(checkouts: Checkouts) -> None:
    """Once the commits are undone, such a path exists nowhere, so the advice doesn't try to put it back."""
    session, code, _ = checkouts
    path = f"{TASK.task_notes_dir}/P.md"
    committed(code, path, "src/main.py")
    git(code, "rm", "-q", path)
    commit_unchecked(code, "remove it again")
    advice = refusal_of(lambda: push_check(session, code, session.agent_task_branch)).splitlines()
    commands = [line.strip() for line in advice if line.strip().startswith("git -C")]

    for command in commands:
        environ = {**os.environ, "AGENT_PROJECT_DIR": str(code)}
        subprocess.run(["sh", "-c", command], cwd=code, env=environ, check=True, capture_output=True)
    commit_unchecked(code, "feat: main")

    assert len(commands) == 1
    push_check(session, code, session.agent_task_branch)


def test_a_merge_of_another_tasks_newer_notes_from_origin_is_accepted(checkouts: Checkouts, tmp_path: Path) -> None:
    """A pull without --rebase: the other task's commit is already on origin, so it isn't in the push."""
    session, _, notes = checkouts
    other = tmp_path / "other-role"
    url = git(notes, "remote", "get-url", "origin").stdout.strip()
    git(tmp_path, "clone", "-q", "-b", session.agent_notes_branch, url, str(other))
    committed(other, f"{OTHER_TASK.task_notes_dir}/PROGRESS.md")
    pushed(other)
    committed(notes, f"{TASK.task_notes_dir}/PROGRESS.md")
    git(
        notes,
        "-c",
        "core.hooksPath=/dev/null",
        "pull",
        "-q",
        "--no-rebase",
        "--no-edit",
        "origin",
        session.agent_notes_branch,
    )

    push_check(session, notes)


def test_another_tasks_notes_changed_by_a_merge_itself_are_refused(checkouts: Checkouts) -> None:
    """git log lists nothing for a merge commit, so what the push leaves is judged too."""
    session, _, notes = checkouts
    git(notes, "switch", "-q", "-c", "side")
    committed(notes, f"{TASK.task_notes_dir}/side.md")
    git(notes, "switch", "-q", session.agent_notes_branch)
    committed(notes, f"{TASK.task_notes_dir}/main.md")
    git(notes, "-c", "core.hooksPath=/dev/null", "merge", "-q", "--no-ff", "--no-commit", "side")
    theirs = f"{OTHER_TASK.task_notes_dir}/EVIL.md"
    stage(notes, theirs)
    commit_unchecked(notes, "merge side")

    assert f"    {theirs}" in refusal_of(lambda: push_check(session, notes))


def test_moving_another_tasks_file_into_own_folder_is_refused(checkouts: Checkouts) -> None:
    """A rename deletes the file in the other task's folder; git's rename detection would list only the new
    path, inside this task's folder."""
    session, _, notes = checkouts
    theirs = f"{OTHER_TASK.task_notes_dir}/PROGRESS.md"
    committed(notes, theirs)
    pushed(notes)
    git(notes, "mv", theirs, f"{TASK.task_notes_dir}/x.md")
    commit_unchecked(notes, "move")

    assert f"    {theirs}" in refusal_of(lambda: push_check(session, notes))


def test_replacing_another_tasks_file_with_a_link_is_refused(checkouts: Checkouts) -> None:
    """A type change: the file in the other task's folder becomes a link, its content gone."""
    session, _, notes = checkouts
    theirs = f"{OTHER_TASK.task_notes_dir}/PROGRESS.md"
    committed(notes, theirs)
    pushed(notes)
    (notes / theirs).unlink()
    (notes / theirs).symlink_to("elsewhere")
    git(notes, "add", theirs)
    commit_unchecked(notes, "link")

    assert f"    {theirs}" in refusal_of(lambda: push_check(session, notes))


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
        "prepare-commit-msg: refusing\n\n  git passed no message file.\n"
    )


# --- STATE.json, judged by pre-push -------------------------------------------

STATE_PATH = f"{TASK.task_notes_dir}/STATE.json"
IMPLEMENT = TaskState(lifecycle=FEATURE, state="implement", note="Approved.")
REVIEW = IMPLEMENT.after("submit", "Ready for review.", "dev")


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
        (IMPLEMENT, REVIEW.after("approve", "LGTM", "reviewer"), "implement can't go to deliver"),
        (
            IMPLEMENT,
            TaskState(lifecycle=BUGFIX, state="review", note="x"),
            "The lifecycle can't change. It is feature.",
        ),
        (REVIEW, IMPLEMENT, "The task is assigned to the reviewer, not the dev. It is in review."),
    ],
    ids=["two turns in one push", "another lifecycle", "a pushed turn reverted"],
)
def test_an_illegal_change_is_refused_saying_why_and_how_to_undo_it(
    checkouts: Checkouts, before: TaskState, after: TaskState, reason: str
) -> None:
    session, _, notes = checkouts
    commit_state(notes, before)
    pushed(notes)
    commit_state(notes, after)

    refusal = refusal_of(lambda: push_check(session, notes))

    assert f"{STATE_PATH} can't change this way." in refusal and reason in refusal
    origin_sha = git(notes, "rev-parse", f"origin/{session.agent_notes_branch}").stdout.strip()
    restore = f"--source={origin_sha} --staged --worktree -- {STATE_PATH}"
    assert f'git -C "$AGENT_NOTES_DIR" reset --soft {origin_sha}' in refusal
    assert f'git -C "$AGENT_NOTES_DIR" restore {restore}' in refusal


def test_the_task_state_advice_still_works_after_the_human_moves_it(checkouts: Checkouts, tmp_path: Path) -> None:
    """A hand edit is refused. Then the human moves the task on origin, and following the advice pulls that in
    without a conflict."""
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)
    pushed(notes)
    commit_state(notes, IMPLEMENT.moved("done", "Skip it."), f"{TASK.task_notes_dir}/PROGRESS.md")
    advice = refusal_of(lambda: push_check(session, notes)).splitlines()
    human = tmp_path / "human"
    url = git(notes, "remote", "get-url", "origin").stdout.strip()
    git(tmp_path, "clone", "-q", "-b", session.agent_notes_branch, url, str(human))
    commit_state(human, IMPLEMENT.moved("blocked", "Wait for me."))
    pushed(human)
    git(notes, "fetch", "-q", "origin")

    for command in (line.strip() for line in advice if line.strip().startswith("git -C")):
        environ = {**os.environ, "AGENT_NOTES_DIR": str(notes)}
        subprocess.run(["sh", "-c", command], cwd=notes, env=environ, check=True, capture_output=True)
    commit_unchecked(notes, "progress")
    git(notes, "-c", "core.hooksPath=/dev/null", "pull", "-q", "--rebase", "origin", session.agent_notes_branch)

    push_check(session, notes)
    assert TaskState.parse((notes / STATE_PATH).read_text(), STATE_PATH).state == "blocked"


def test_creating_the_task_state_is_refused(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)

    assert "It can't be created in the sandbox." in refusal_of(lambda: push_check(session, notes))


def test_deleting_the_task_state_is_refused(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)
    pushed(notes)
    git(notes, "rm", "-q", STATE_PATH)
    commit_unchecked(notes, "drop state")

    assert "It can't be deleted in the sandbox." in refusal_of(lambda: push_check(session, notes))


def test_a_file_that_isnt_a_task_state_is_refused(checkouts: Checkouts) -> None:
    session, _, notes = checkouts
    commit_state(notes, IMPLEMENT)
    pushed(notes)
    (notes / STATE_PATH).write_text("{}")
    git(notes, "add", STATE_PATH)
    commit_unchecked(notes, "bad state")

    assert "is not a task state" in refusal_of(lambda: push_check(session, notes))
