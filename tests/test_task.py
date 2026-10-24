"""foundry/task.py against a real repository on disk, and the `foundry task create` command's report and arguments."""

import os
import re
import subprocess
from pathlib import Path

import pytest

from foundry import cli, task
from foundry.commands.task import report
from foundry.errors import FoundryError
from foundry.git_clone import GitClone
from foundry.task import Task

TEMPLATE = {"TASK.md": "# Task <id>: <title>\n", "PROGRESS.md": "# Progress\n"}


@pytest.fixture
def git_env(tmp_path: Path) -> dict[str, str]:
    """git with a throwaway identity, and none of the developer's own config."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    (home_dir / ".gitconfig").write_text("[user]\n\tname = Owner\n\temail = owner@example.com\n")
    return {"PATH": os.environ["PATH"], "HOME": str(home_dir), "GIT_CONFIG_NOSYSTEM": "1"}


def git(env: dict[str, str], *args: str) -> str:
    return subprocess.run(["git", *args], env=env, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def origin_dir(tmp_path: Path, git_env) -> Path:
    """A project repository with one commit on main, and agent-notes holding an earlier task."""
    origin_dir = tmp_path / "origin.git"
    seed_dir = tmp_path / "seed"
    git(git_env, "init", "--quiet", "--bare", "--initial-branch=main", str(origin_dir))
    git(git_env, "init", "--quiet", "--initial-branch=main", str(seed_dir))
    (seed_dir / "README.md").write_text("code\n")
    git(git_env, "-C", str(seed_dir), "add", ".")
    git(git_env, "-C", str(seed_dir), "commit", "--quiet", "-m", "init")
    git(git_env, "-C", str(seed_dir), "switch", "--quiet", "--orphan", task.NOTES_BRANCH)
    (seed_dir / ".agent" / "t0").mkdir(parents=True)
    (seed_dir / ".agent" / "t0" / "TASK.md").write_text("an earlier task\n")
    git(git_env, "-C", str(seed_dir), "add", ".agent")
    git(git_env, "-C", str(seed_dir), "commit", "--quiet", "-m", "T0")
    git(git_env, "-C", str(seed_dir), "push", "--quiet", str(origin_dir), "main", task.NOTES_BRANCH)
    return origin_dir


def create(origin_dir: Path, git_env: dict[str, str], task_id: str = "T1") -> None:
    scratch_dir = origin_dir.parent / f"scratch-{task_id}"
    scratch_dir.mkdir()
    task.create(GitClone.init(str(origin_dir), scratch_dir, git_env), Task(task_id), TEMPLATE)


def files_on(origin_dir: Path, git_env: dict[str, str], branch: str) -> dict[str, str]:
    paths = git(git_env, f"--git-dir={origin_dir}", "ls-tree", "-r", "--name-only", branch).splitlines()
    return {path: git(git_env, f"--git-dir={origin_dir}", "show", f"{branch}:{path}") + "\n" for path in paths}


def head(origin_dir: Path, git_env: dict[str, str], branch: str) -> str:
    return git(git_env, f"--git-dir={origin_dir}", "rev-parse", f"refs/heads/{branch}")


# --- Task -----------------------------------------------------------------------


def test_a_task_is_its_lowercased_id_its_branch_and_its_notes_folder() -> None:
    a_task = Task("WCF-0042")
    assert (a_task.id, a_task.branch, a_task.notes_dir) == ("wcf-0042", "task/wcf-0042", ".agent/wcf-0042")
    assert a_task == Task("wcf-0042")


@pytest.mark.parametrize("task_id", ["WCF-0042", "fix-login.2", "t_1", "7"])
def test_valid_task_ids(task_id: str) -> None:
    assert Task(task_id).id == task_id.lower()


@pytest.mark.parametrize(
    "task_id", ["", "-x", ".x", "feat/x", "a b", "a..b", "x.", "x.lock", "X.LOCK", "ü", "x~1", "x:y", "\u212a1"]
)
def test_task_ids_that_are_not_valid_branch_names_are_refused(task_id: str) -> None:
    with pytest.raises(FoundryError, match=re.escape(f"task id {task_id!r} is not valid")):
        Task(task_id)


# --- create ---------------------------------------------------------------------


def test_a_task_is_its_branch_from_the_default_branch_and_the_template_in_its_notes_folder(origin_dir, git_env) -> None:
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)

    create(origin_dir, git_env)

    assert head(origin_dir, git_env, "task/t1") == head(origin_dir, git_env, "main")
    assert files_on(origin_dir, git_env, task.NOTES_BRANCH) == {
        ".agent/t0/TASK.md": "an earlier task\n",
        ".agent/t1/PROGRESS.md": "# Progress\n",
        ".agent/t1/TASK.md": "# Task <id>: <title>\n",
    }
    notes_parent = git(git_env, f"--git-dir={origin_dir}", "rev-parse", f"{task.NOTES_BRANCH}^")
    assert notes_parent == notes_before


def test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files(origin_dir, git_env) -> None:
    git(git_env, f"--git-dir={origin_dir}", "branch", "--quiet", "-D", task.NOTES_BRANCH)

    create(origin_dir, git_env)

    assert files_on(origin_dir, git_env, task.NOTES_BRANCH) == {
        ".agent/t1/PROGRESS.md": "# Progress\n",
        ".agent/t1/TASK.md": "# Task <id>: <title>\n",
    }
    assert git(git_env, f"--git-dir={origin_dir}", "rev-list", "--count", task.NOTES_BRANCH) == "1"


def test_an_existing_task_branch_is_refused_and_nothing_is_written(origin_dir, git_env) -> None:
    git(git_env, f"--git-dir={origin_dir}", "branch", "task/t1", "main")
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)

    with pytest.raises(FoundryError, match=r"^task t1 already exists: there is a task/t1 branch$"):
        create(origin_dir, git_env)
    assert head(origin_dir, git_env, task.NOTES_BRANCH) == notes_before


def test_an_existing_notes_folder_is_refused_and_no_branch_is_made(origin_dir, git_env) -> None:
    with pytest.raises(FoundryError, match=r"^task t0 already exists: agent-notes has .agent/t0/$"):
        create(origin_dir, git_env, "T0")
    assert "task/t0" not in git(git_env, f"--git-dir={origin_dir}", "branch", "--list")


def test_a_repository_with_no_commits_is_refused(tmp_path: Path, git_env) -> None:
    empty_dir = tmp_path / "empty.git"
    git(git_env, "init", "--quiet", "--bare", str(empty_dir))

    with pytest.raises(FoundryError, match=r"^the repository has no commits to branch task/t1 from$"):
        create(empty_dir, git_env)


def test_an_unreachable_repository_fails_with_gits_message(tmp_path: Path, git_env) -> None:
    with pytest.raises(FoundryError, match=r"^git ls-remote failed: .*does not appear to be a git repository"):
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


def test_the_report_says_what_was_created_and_how_to_run_it() -> None:
    assert report("store", Task("T1")) == ["created task t1 in store", "run it with: foundry run store ROLE t1"]


def test_create_takes_a_project_and_a_task() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "T1"])
    assert (args.project_name, args.task_id) == ("store", "T1")


# --- GitClone: what task.create can't reach ---------------------------------------


def test_a_push_of_no_branches_is_refused(tmp_path: Path, git_env) -> None:
    clone_dir = tmp_path / "clone"  # GitClone.init needs an empty folder; tmp_path holds git_env's home/
    clone_dir.mkdir()
    clone = GitClone.init(str(tmp_path / "origin.git"), clone_dir, git_env)
    with pytest.raises(ValueError, match="at least one branch"):
        clone.push_atomic(from_remote={}, from_local=[])
