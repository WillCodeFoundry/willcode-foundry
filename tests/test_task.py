"""foundry/task.py, and ProjectTasks against a real repository on disk, and the `foundry task` commands' reports
and arguments."""

import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from agent_runtime.git import GitError
from foundry import cli, task
from foundry.commands.task import CLOSED, CREATED, REOPENED, Outcome, report
from foundry.errors import FoundryError
from foundry.project_clone import ProjectClone
from foundry.project_tasks import ProjectTasks, TaskNotFoundError
from foundry.task import Status, Task

TEMPLATE = {"TASK.md": "# Task <id>: <title>\n", "PROGRESS.md": "# Progress\n"}
SIGNING_KEY = "ssh-ed25519 AAAATESTKEY"

# Stands in for ssh-keygen as git's SSH signer: git runs it as <program> -Y sign ... -f <key file> ... <payload>,
# and it writes <payload>.sig holding the key it was asked to sign with, so a test can see which key signed.
SIGNER = """#!/bin/sh
while [ $# -gt 1 ]; do case "$1" in -f) key="$2"; shift 2 ;; *) shift ;; esac; done
printf '%s\\n' "-----BEGIN SSH SIGNATURE-----" "$(cat "$key")" "-----END SSH SIGNATURE-----" > "$1.sig"
"""


def write_gitconfig(home_dir: Path, *, signing_key: str | None = SIGNING_KEY) -> None:
    """Your git config: an identity, your signing key unless None, and SIGNER standing in for ssh-keygen."""
    signer = home_dir / "signer"
    signer.write_text(SIGNER)
    signer.chmod(0o755)
    user = "[user]\n\tname = Owner\n\temail = owner@example.com\n"
    if signing_key is not None:
        user += f"\tsigningkey = key::{signing_key}\n"
    (home_dir / ".gitconfig").write_text(f'{user}[gpg "ssh"]\n\tprogram = {signer}\n')


@pytest.fixture
def git_env(tmp_path: Path) -> dict[str, str]:
    """git with a throwaway identity, and none of the developer's own config."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    write_gitconfig(home_dir)
    return {"PATH": os.environ["PATH"], "HOME": str(home_dir), "GIT_CONFIG_NOSYSTEM": "1"}


def git(env: dict[str, str], *args: str) -> str:
    return subprocess.run(["git", *args], env=env, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def origin_dir(tmp_path: Path, git_env) -> Path:
    """A project repository with one commit on main, and agent-notes holding an open task t0 and a closed one c0."""
    origin_dir = tmp_path / "origin.git"
    seed_dir = tmp_path / "seed"
    git(git_env, "init", "--quiet", "--bare", "--initial-branch=main", str(origin_dir))
    git(git_env, "init", "--quiet", "--initial-branch=main", str(seed_dir))
    (seed_dir / "README.md").write_text("code\n")
    git(git_env, "-C", str(seed_dir), "add", ".")
    git(git_env, "-C", str(seed_dir), "commit", "--quiet", "-m", "init")
    git(git_env, "-C", str(seed_dir), "switch", "--quiet", "--orphan", task.NOTES_BRANCH)
    for status_dir, task_id in (("open", "t0"), ("closed", "c0")):
        (seed_dir / ".agent" / "tasks" / status_dir / task_id).mkdir(parents=True)
        (seed_dir / ".agent" / "tasks" / status_dir / task_id / "TASK.md").write_text(f"{task_id}\n")
    git(git_env, "-C", str(seed_dir), "add", ".agent")
    git(git_env, "-C", str(seed_dir), "commit", "--quiet", "-m", "T0")
    git(git_env, "-C", str(seed_dir), "push", "--quiet", str(origin_dir), "main", task.NOTES_BRANCH)
    return origin_dir


def clone_in(parent_dir: Path, git_env: dict[str, str], url: str) -> ProjectClone:
    """A ProjectClone of ``url`` in a new folder in ``parent_dir``."""
    return ProjectClone.init(url, Path(tempfile.mkdtemp(dir=parent_dir, prefix="scratch-")), git_env)


def tasks_of(origin_dir: Path, git_env: dict[str, str]) -> ProjectTasks:
    """The tasks of ``origin_dir``, through a clone of their own, so each sees the repository as it is now."""
    return ProjectTasks(clone_in(origin_dir.parent, git_env, str(origin_dir)))


def create(origin_dir: Path, git_env: dict[str, str], task_id: str = "T1") -> Task:
    return tasks_of(origin_dir, git_env).create_task(task_id, TEMPLATE)


def branch_files(origin_dir: Path, git_env: dict[str, str], branch: str) -> dict[str, str]:
    paths = git(git_env, f"--git-dir={origin_dir}", "ls-tree", "-r", "--name-only", branch).splitlines()
    return {path: git(git_env, f"--git-dir={origin_dir}", "show", f"{branch}:{path}") + "\n" for path in paths}


def head(origin_dir: Path, git_env: dict[str, str], branch: str) -> str:
    return git(git_env, f"--git-dir={origin_dir}", "rev-parse", f"refs/heads/{branch}")


def assert_notes_signed_with_your_key(origin_dir: Path, git_env: dict[str, str]) -> None:
    commit = git(git_env, f"--git-dir={origin_dir}", "cat-file", "commit", task.NOTES_BRANCH)
    assert f"gpgsig -----BEGIN SSH SIGNATURE-----\n {SIGNING_KEY}\n" in commit


# --- Task -----------------------------------------------------------------------


def test_an_open_task_is_its_lowercased_id_its_branch_and_its_notes_folder_under_open() -> None:
    a_task = Task.as_open("WCF-0042")
    assert (a_task.id, a_task.branch, a_task.task_notes_dir, a_task.task_file, a_task.turn_file) == (
        "wcf-0042",
        "task/wcf-0042",
        ".agent/tasks/open/wcf-0042",
        ".agent/tasks/open/wcf-0042/TASK.md",
        ".agent/tasks/open/wcf-0042/TURN",
    )
    assert a_task == Task("wcf-0042", Status.OPEN)


def test_a_closed_task_s_notes_folder_is_under_closed() -> None:
    a_task = Task.as_closed("WCF-0042")
    assert (a_task.branch, a_task.task_notes_dir, a_task.task_file, a_task.turn_file) == (
        "task/wcf-0042",
        ".agent/tasks/closed/wcf-0042",
        ".agent/tasks/closed/wcf-0042/TASK.md",
        ".agent/tasks/closed/wcf-0042/TURN",
    )


@pytest.mark.parametrize("task_id", ["WCF-0042", "fix-login.2", "t_1", "7"])
def test_valid_task_ids(task_id: str) -> None:
    assert Task.as_open(task_id).id == task_id.lower()


@pytest.mark.parametrize(
    "task_id", ["", "-x", ".x", "feat/x", "a b", "a..b", "x.", "x.lock", "X.LOCK", "ü", "x~1", "x:y", "\u212a1"]
)
def test_task_ids_that_are_not_valid_branch_names_are_refused(task_id: str) -> None:
    with pytest.raises(
        FoundryError, match=re.escape(f"task id {(task_id.lower() if task_id.isascii() else task_id)!r} is not valid")
    ):
        Task.as_open(task_id)


# --- create ---------------------------------------------------------------------


def test_a_task_is_its_branch_from_the_default_branch_and_the_template_in_its_notes_folder(origin_dir, git_env) -> None:
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)

    assert create(origin_dir, git_env) == Task.as_open("t1")

    assert head(origin_dir, git_env, "task/t1") == head(origin_dir, git_env, "main")
    assert branch_files(origin_dir, git_env, task.NOTES_BRANCH) == {
        ".agent/tasks/closed/c0/TASK.md": "c0\n",
        ".agent/tasks/open/t0/TASK.md": "t0\n",
        ".agent/tasks/open/t1/PROGRESS.md": "# Progress\n",
        ".agent/tasks/open/t1/TASK.md": "# Task <id>: <title>\n",
    }
    notes_parent = git(git_env, f"--git-dir={origin_dir}", "rev-parse", f"{task.NOTES_BRANCH}^")
    assert notes_parent == notes_before


def test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files(origin_dir, git_env) -> None:
    git(git_env, f"--git-dir={origin_dir}", "branch", "--quiet", "-D", task.NOTES_BRANCH)

    create(origin_dir, git_env)

    assert branch_files(origin_dir, git_env, task.NOTES_BRANCH) == {
        ".agent/tasks/open/t1/PROGRESS.md": "# Progress\n",
        ".agent/tasks/open/t1/TASK.md": "# Task <id>: <title>\n",
    }
    assert git(git_env, f"--git-dir={origin_dir}", "rev-list", "--count", task.NOTES_BRANCH) == "1"


def test_the_tasks_notes_commit_is_signed_with_your_signing_key(origin_dir, git_env) -> None:
    create(origin_dir, git_env)

    assert_notes_signed_with_your_key(origin_dir, git_env)


def test_without_a_signing_key_nothing_is_pushed(origin_dir, git_env) -> None:
    write_gitconfig(Path(git_env["HOME"]), signing_key=None)
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)

    with pytest.raises(
        GitError, match=r"(?s)^git -C \S+ commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"
    ):
        create(origin_dir, git_env)
    assert head(origin_dir, git_env, task.NOTES_BRANCH) == notes_before
    assert "task/t1" not in git(git_env, f"--git-dir={origin_dir}", "branch", "--list")


def test_an_existing_task_branch_is_refused_and_nothing_is_written(origin_dir, git_env) -> None:
    git(git_env, f"--git-dir={origin_dir}", "branch", "task/t1", "main")
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)

    with pytest.raises(FoundryError, match=r"^task t1 already exists: there is a task/t1 branch$"):
        create(origin_dir, git_env)
    assert head(origin_dir, git_env, task.NOTES_BRANCH) == notes_before


@pytest.mark.parametrize("task_id, found", [("T0", "open/t0"), ("C0", "closed/c0")])
def test_an_existing_notes_folder_open_or_closed_is_refused_and_nothing_is_pushed(
    origin_dir, git_env, task_id: str, found: str
) -> None:
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)
    with pytest.raises(
        FoundryError, match=rf"^task {task_id.lower()} already exists: agent-notes has .agent/tasks/{found}/$"
    ):
        create(origin_dir, git_env, task_id)
    assert f"task/{task_id.lower()}" not in git(git_env, f"--git-dir={origin_dir}", "branch", "--list")
    assert head(origin_dir, git_env, task.NOTES_BRANCH) == notes_before


def test_a_closed_task_that_kept_its_branch_is_refused_naming_its_notes_folder(origin_dir, git_env) -> None:
    git(git_env, f"--git-dir={origin_dir}", "branch", "task/c0", "main")

    with pytest.raises(FoundryError, match=r"^task c0 already exists: agent-notes has .agent/tasks/closed/c0/$"):
        create(origin_dir, git_env, "c0")


def test_a_repository_with_no_commits_is_refused(tmp_path: Path, git_env) -> None:
    empty_dir = tmp_path / "empty.git"
    git(git_env, "init", "--quiet", "--bare", str(empty_dir))

    with pytest.raises(FoundryError, match=r"^the repository has no commits to branch task/t1 from$"):
        create(empty_dir, git_env)


def test_an_unreachable_repository_fails_with_gits_message(tmp_path: Path, git_env) -> None:
    with pytest.raises(
        GitError, match=r"^git -C \S+ ls-remote --heads origin failed: .*does not appear to be a git repo"
    ):
        create(tmp_path / "missing.git", git_env)


# --- load_template ----------------------------------------------------------------


def test_the_template_is_every_file_directly_in_its_folder(tmp_path: Path) -> None:
    (tmp_path / "TASK.md").write_text("# Task\n")
    (tmp_path / "PROGRESS.md").write_text("# Progress\n")
    (tmp_path / "drafts").mkdir()
    (tmp_path / "drafts" / "ignored.md").write_text("no\n")

    assert task.load_template(tmp_path) == {"PROGRESS.md": "# Progress\n", "TASK.md": "# Task\n"}


def test_a_template_without_a_task_md_is_refused(tmp_path: Path) -> None:
    template_dir = tmp_path / "task-template"
    template_dir.mkdir()
    (template_dir / "PROGRESS.md").write_text("# Progress\n")

    with pytest.raises(FoundryError, match=r"task-template has no TASK\.md; every task needs one$"):
        task.load_template(template_dir)


def test_a_missing_template_folder_is_named(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match=r"task-template is missing$"):
        task.load_template(tmp_path / "task-template")


# --- the command ------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome, changed, lines",
    [
        (CREATED, Task.as_open("t1"), ["created task t1 in store", "run it with: foundry run store t1"]),
        (CLOSED, Task.as_closed("t1"), ["closed task t1 in store", "reopen it with: foundry task reopen store t1"]),
        (REOPENED, Task.as_open("t1"), ["reopened task t1 in store", "run it with: foundry run store t1"]),
    ],
)
def test_the_report_says_what_was_done_and_what_comes_next(outcome: Outcome, changed: Task, lines: list[str]) -> None:
    assert report(outcome, "store", changed) == lines


def test_create_takes_a_project_and_a_task() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "T1"])
    assert (args.project_name, args.task_id) == ("store", "T1")


@pytest.mark.parametrize("action", ["close", "reopen"])
def test_close_and_reopen_take_a_project_and_a_task(action: str) -> None:
    args = cli.build_parser().parse_args(["task", action, "store", "T1"])
    assert (args.project_name, args.task_id) == ("store", "T1")


# --- ProjectClone: what ProjectTasks can't reach ----------------------------------------


def test_a_push_of_no_branches_is_refused(tmp_path: Path, git_env) -> None:
    clone = clone_in(tmp_path, git_env, str(tmp_path / "origin.git"))
    with pytest.raises(AssertionError, match="at least one branch"):
        clone.push_atomic(from_remote={}, from_local=[])


def test_move_dir_refuses_an_existing_destination(tmp_path: Path, git_env) -> None:
    clone = clone_in(tmp_path, git_env, str(tmp_path / "origin.git"))
    clone.write({"a/one.md": "1\n", "b/two.md": "2\n"})

    with pytest.raises(FileExistsError):
        clone.move_dir("a", "b")


# --- read_task_turn ---------------------------------------------------------------------


def turn_of(origin_dir: Path, git_env: dict[str, str], task_id: str) -> str:
    return tasks_of(origin_dir, git_env).read_task_turn(task_id)


def test_a_new_task_s_turn_is_the_template_s(origin_dir, git_env) -> None:
    tasks_of(origin_dir, git_env).create_task("T1", {**TEMPLATE, "TURN": "dev\n"})

    assert turn_of(origin_dir, git_env, "T1") == "dev"


def test_a_task_without_a_turn_says_to_name_the_role(origin_dir, git_env) -> None:
    with pytest.raises(FoundryError, match=r"task t0 has no turn: agent-notes has no .agent/tasks/open/t0/TURN.*Name"):
        turn_of(origin_dir, git_env, "t0")


def test_a_closed_task_s_turn_is_read_from_its_closed_notes_folder(origin_dir, git_env) -> None:
    with pytest.raises(FoundryError, match=r"task c0 has no turn: agent-notes has no .agent/tasks/closed/c0/TURN"):
        turn_of(origin_dir, git_env, "c0")


def test_a_task_that_doesn_t_exist_has_no_turn_to_read(origin_dir, git_env) -> None:
    with pytest.raises(TaskNotFoundError):
        turn_of(origin_dir, git_env, "t9")


def test_the_task_template_starts_with_the_planner_s_turn() -> None:
    template = task.load_template(Path(__file__).parents[1] / "config" / "task-template")
    assert template[task.TURN_FILE].strip() == "planner"


# --- get_task_by_id ---------------------------------------------------------------------


@pytest.mark.parametrize("task_id, found", [("T0", Task.as_open("t0")), ("c0", Task.as_closed("c0"))])
def test_a_task_has_the_status_of_the_folder_holding_its_notes(origin_dir, git_env, task_id: str, found) -> None:
    assert tasks_of(origin_dir, git_env).get_task_by_id(task_id) == found


def test_a_task_in_neither_folder_is_not_found_naming_both(origin_dir, git_env) -> None:
    with pytest.raises(
        TaskNotFoundError,
        match=r"^task t9 doesn't exist: agent-notes has neither .agent/tasks/open/t9/ nor .agent/tasks/closed/t9/$",
    ):
        tasks_of(origin_dir, git_env).get_task_by_id("t9")


def test_a_repository_without_a_notes_branch_has_no_tasks(tmp_path: Path, git_env) -> None:
    origin_dir = tmp_path / "bare.git"
    git(git_env, "init", "--quiet", "--bare", str(origin_dir))
    with pytest.raises(TaskNotFoundError):
        tasks_of(origin_dir, git_env).get_task_by_id("t1")


def test_a_task_in_both_folders_is_refused_naming_both(origin_dir, git_env) -> None:
    push_notes(origin_dir, git_env, {".agent/tasks/closed/t0/TASK.md": "t0\n"})

    with pytest.raises(FoundryError, match=r"^task t0 is both open and closed: .*open/t0/ and .*closed/t0/$") as error:
        tasks_of(origin_dir, git_env).get_task_by_id("t0")
    assert not isinstance(error.value, TaskNotFoundError)


# --- close_task, reopen_task -------------------------------------------------------------


def notes_commits(origin_dir: Path, git_env: dict[str, str]) -> list[str]:
    return git(git_env, f"--git-dir={origin_dir}", "log", "--format=%s", task.NOTES_BRANCH).splitlines()


def push_notes(origin_dir: Path, git_env: dict[str, str], files: dict[str, str]) -> None:
    """Add ``files``, by path, to agent-notes with a plain git push, as an agent would."""
    work = Path(tempfile.mkdtemp(dir=origin_dir.parent, prefix="seed-"))
    git(git_env, "clone", "--quiet", "--branch", task.NOTES_BRANCH, str(origin_dir), str(work))
    for path, text in files.items():
        (work / path).parent.mkdir(parents=True, exist_ok=True)
        (work / path).write_bytes(text.encode())
    git(git_env, "-C", str(work), "add", ".")
    git(git_env, "-C", str(work), "commit", "--quiet", "-m", "more")
    git(git_env, "-C", str(work), "push", "--quiet", "origin", task.NOTES_BRANCH)


def tree(origin_dir: Path, git_env: dict[str, str]) -> dict[str, str]:
    """Each file on agent-notes, by path: its mode and blob."""
    listing = git(git_env, f"--git-dir={origin_dir}", "ls-tree", "-r", task.NOTES_BRANCH).splitlines()
    return {
        path: mode_type_blob.replace(" blob ", " ") for mode_type_blob, path in (line.split("\t") for line in listing)
    }


def test_close_moves_the_notes_folder_unchanged_in_one_signed_commit(origin_dir, git_env) -> None:
    push_notes(
        origin_dir,
        git_env,
        {".agent/tasks/open/t0/sub/NOTE.md": "n\n", ".agent/tasks/open/t0/PROGRESS.md": "p\n"},
    )
    before = branch_files(origin_dir, git_env, task.NOTES_BRANCH)
    commits_before = len(notes_commits(origin_dir, git_env))
    branches_before = git(git_env, f"--git-dir={origin_dir}", "branch", "--list")

    assert tasks_of(origin_dir, git_env).close_task("T0") == Task.as_closed("t0")

    expected = {path.replace("tasks/open/t0", "tasks/closed/t0"): text for path, text in before.items()}
    assert branch_files(origin_dir, git_env, task.NOTES_BRANCH) == expected
    assert ".agent/tasks/closed/t0/sub/NOTE.md" in expected
    assert notes_commits(origin_dir, git_env)[0] == "Close task t0"
    assert len(notes_commits(origin_dir, git_env)) == commits_before + 1
    assert_notes_signed_with_your_key(origin_dir, git_env)
    assert git(git_env, f"--git-dir={origin_dir}", "branch", "--list") == branches_before


def test_reopen_makes_the_reverse_move_in_one_signed_commit(origin_dir, git_env) -> None:
    before = branch_files(origin_dir, git_env, task.NOTES_BRANCH)

    assert tasks_of(origin_dir, git_env).reopen_task("C0") == Task.as_open("c0")

    expected = {path.replace("tasks/closed/c0", "tasks/open/c0"): text for path, text in before.items()}
    assert branch_files(origin_dir, git_env, task.NOTES_BRANCH) == expected
    assert notes_commits(origin_dir, git_env)[0] == "Reopen task c0"
    assert_notes_signed_with_your_key(origin_dir, git_env)


def test_a_move_keeps_files_your_git_config_would_ignore_or_convert(origin_dir, git_env) -> None:
    push_notes(
        origin_dir,
        git_env,
        {".agent/tasks/open/t0/run.log": "log\n", ".agent/tasks/open/t0/crlf.md": "a\r\nb\r\n"},
    )
    home_dir = Path(git_env["HOME"])
    (home_dir / "excludes").write_text("*.log\n")
    with (home_dir / ".gitconfig").open("a") as gitconfig:
        gitconfig.write(f"[core]\n\texcludesFile = {home_dir / 'excludes'}\n\tautocrlf = input\n")
    before = tree(origin_dir, git_env)

    tasks_of(origin_dir, git_env).close_task("t0")

    assert tree(origin_dir, git_env) == {
        path.replace("tasks/open/t0", "tasks/closed/t0"): entry for path, entry in before.items()
    }


@pytest.mark.parametrize(
    "operation, task_id, message",
    [
        (ProjectTasks.close_task, "c0", "^task c0 is already closed$"),
        (ProjectTasks.close_task, "t9", r"^task t9 doesn't exist: "),
        (ProjectTasks.reopen_task, "t0", "^task t0 is already open$"),
        (ProjectTasks.reopen_task, "t9", r"^task t9 doesn't exist: "),
    ],
)
def test_close_and_reopen_refuse_and_push_nothing(origin_dir, git_env, operation, task_id, message) -> None:
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)

    with pytest.raises(FoundryError, match=message):
        operation(tasks_of(origin_dir, git_env), task_id)
    assert head(origin_dir, git_env, task.NOTES_BRANCH) == notes_before


@pytest.mark.parametrize(
    "operation, task_id", [(ProjectTasks.close_task, "t0"), (ProjectTasks.reopen_task, "c0")], ids=["close", "reopen"]
)
def test_without_a_signing_key_close_and_reopen_push_nothing(origin_dir, git_env, operation, task_id) -> None:
    write_gitconfig(Path(git_env["HOME"]), signing_key=None)
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)

    with pytest.raises(GitError, match=r"(?s)commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"):
        operation(tasks_of(origin_dir, git_env), task_id)
    assert head(origin_dir, git_env, task.NOTES_BRANCH) == notes_before
