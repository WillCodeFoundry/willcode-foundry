"""foundry/task.py, and ProjectTasks against a real repository on disk, and the `foundry task` commands' reports
and arguments."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from agent_runtime.git import GitError
from foundry import cli, task
from foundry.commands.task import (
    CLOSED,
    CREATED,
    REOPENED,
    Outcome,
    ProjectListing,
    chosen_projects,
    filter_project_listing,
    handoff_lines,
    listing_lines,
    read_listings_and_errors,
    report,
    require_valid_handoff_args,
)
from foundry.config import Config, Project, Role
from foundry.errors import FoundryError
from foundry.project_clone import NotOnBranchError, ProjectClone
from foundry.project_tasks import NoTurnError, ProjectTasks, TaskNotFoundError, TaskSummary, log_with_turn_entry
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


def clone_in(parent_dir: Path, git_env: dict[str, str], url: str) -> ProjectClone:
    """A ProjectClone of ``url`` in a new folder in ``parent_dir``."""
    return ProjectClone.init(url, Path(tempfile.mkdtemp(dir=parent_dir, prefix="scratch-")), git_env)


def project_tasks_of(repository_dir: Path, git_env: dict[str, str]) -> ProjectTasks:
    """The tasks of the repository at ``repository_dir``, as the project store, through a clone of their own."""
    return ProjectTasks(clone_in(repository_dir.parent, git_env, str(repository_dir)), "store")


class ProjectRepository:
    """Stands in for the GitHub repository behind the project store: a bare repository at ``path``.

    Its main has one commit, and its agent-notes holds ``open_task`` and ``closed_task``, each with a TASK.md. Each
    method sees it as it is now. git runs in ``git_env``.
    """

    open_task = Task.as_open("tst-0000")
    closed_task = Task.as_closed("cls-0000")

    def __init__(self, path: Path, git_env: dict[str, str]) -> None:
        self.path = path
        self.git_env = git_env

    def git(self, *args: str) -> str:
        """git's stripped output, run on the bare repository."""
        return git(self.git_env, f"--git-dir={self.path}", *args)

    def clone(self, env: dict[str, str] | None = None) -> ProjectClone:
        """A ProjectClone of it in a new folder, with git run in ``env``, or ``git_env``."""
        return clone_in(self.path.parent, env or self.git_env, str(self.path))

    def fetched_clone(self) -> ProjectClone:
        """A ProjectClone of it, with agent-notes fetched."""
        clone = self.clone()
        clone.fetch_branch(task.NOTES_BRANCH)
        return clone

    def project_tasks(self, env: dict[str, str] | None = None) -> ProjectTasks:
        """Its tasks, through a clone of their own, with git run in ``env``, or ``git_env``."""
        return ProjectTasks(self.clone(env), "store")

    def edit_notes(self, *, write=None, symlink=None, remove=()) -> None:
        """Commit to agent-notes and push it, as an agent would: files to ``write``, links to ``symlink`` (path ->
        target), paths to ``remove``."""
        work_dir = Path(tempfile.mkdtemp(dir=self.path.parent, prefix="edit-"))
        git(self.git_env, "clone", "--quiet", "--branch", task.NOTES_BRANCH, str(self.path), str(work_dir))
        for path, text in (write or {}).items():
            (work_dir / path).parent.mkdir(parents=True, exist_ok=True)
            (work_dir / path).write_text(text)
        for path, target in (symlink or {}).items():
            (work_dir / path).parent.mkdir(parents=True, exist_ok=True)
            (work_dir / path).symlink_to(target)
        for path in remove:
            git(self.git_env, "-C", str(work_dir), "rm", "-rq", path)
        git(self.git_env, "-C", str(work_dir), "add", "-A")
        git(self.git_env, "-C", str(work_dir), "commit", "--quiet", "-m", "edit")
        git(self.git_env, "-C", str(work_dir), "push", "--quiet", "origin", task.NOTES_BRANCH)

    def notes_files(self) -> dict[str, str]:
        """Each file on agent-notes, by path: its text, stripped, then a newline."""
        paths = self.git("ls-tree", "-r", "--name-only", task.NOTES_BRANCH).splitlines()
        return {path: self.git("show", f"{task.NOTES_BRANCH}:{path}") + "\n" for path in paths}

    def notes_tree(self) -> dict[str, str]:
        """Each file on agent-notes, by path: its mode and blob."""
        listing = self.git("ls-tree", "-r", task.NOTES_BRANCH).splitlines()
        return {
            path: mode_type_blob.replace(" blob ", " ")
            for mode_type_blob, path in (line.split("\t") for line in listing)
        }

    def notes_commits(self) -> list[str]:
        """The subject of each commit on agent-notes, newest first."""
        return self.git("log", "--format=%s", task.NOTES_BRANCH).splitlines()

    def head(self, branch: str = task.NOTES_BRANCH) -> str:
        return self.git("rev-parse", f"refs/heads/{branch}")

    def notes_signed_with_your_key(self) -> bool:
        """Whether agent-notes' last commit is signed with SIGNING_KEY."""
        commit = self.git("cat-file", "commit", task.NOTES_BRANCH)
        return f"gpgsig -----BEGIN SSH SIGNATURE-----\n {SIGNING_KEY}\n" in commit


@pytest.fixture
def project_repository(tmp_path: Path, git_env) -> ProjectRepository:
    path = tmp_path / "origin.git"
    seed_dir = tmp_path / "seed"
    git(git_env, "init", "--quiet", "--bare", "--initial-branch=main", str(path))
    git(git_env, "init", "--quiet", "--initial-branch=main", str(seed_dir))
    (seed_dir / "README.md").write_text("code\n")
    git(git_env, "-C", str(seed_dir), "add", ".")
    git(git_env, "-C", str(seed_dir), "commit", "--quiet", "-m", "init")
    git(git_env, "-C", str(seed_dir), "switch", "--quiet", "--orphan", task.NOTES_BRANCH)
    for seeded in (ProjectRepository.open_task, ProjectRepository.closed_task):
        (seed_dir / seeded.task_notes_dir).mkdir(parents=True)
        (seed_dir / seeded.task_file).write_text(f"{seeded.id}\n")
    git(git_env, "-C", str(seed_dir), "add", ".agent")
    git(git_env, "-C", str(seed_dir), "commit", "--quiet", "-m", "T0")
    git(git_env, "-C", str(seed_dir), "push", "--quiet", str(path), "main", task.NOTES_BRANCH)
    return ProjectRepository(path, git_env)


@pytest.fixture
def no_signing_key(git_env) -> None:
    """Your git config, without a signing key."""
    write_gitconfig(Path(git_env["HOME"]), signing_key=None)


def create(project_repository: ProjectRepository, task_id: str = "tst-0001") -> Task:
    return project_repository.project_tasks().create_task(task_id, TEMPLATE)


# --- Task -----------------------------------------------------------------------


def test_an_open_task_is_its_id_its_branch_and_its_task_notes_dir_under_open() -> None:
    a_task = Task.as_open("wcf-0042")
    assert (a_task.id, a_task.branch, a_task.task_notes_dir, a_task.task_file, a_task.turn_file, a_task.log_file) == (
        "wcf-0042",
        "task/wcf-0042",
        ".agent/tasks/open/wcf-0042",
        ".agent/tasks/open/wcf-0042/TASK.md",
        ".agent/tasks/open/wcf-0042/TURN",
        ".agent/tasks/open/wcf-0042/LOG.md",
    )
    assert a_task == Task("wcf-0042", Status.OPEN)


def test_a_closed_task_s_task_notes_dir_is_under_closed() -> None:
    a_task = Task.as_closed("wcf-0042")
    assert (a_task.branch, a_task.task_notes_dir, a_task.task_file, a_task.turn_file) == (
        "task/wcf-0042",
        ".agent/tasks/closed/wcf-0042",
        ".agent/tasks/closed/wcf-0042/TASK.md",
        ".agent/tasks/closed/wcf-0042/TURN",
    )


@pytest.mark.parametrize("task_id", ["wcf-0042", "a-0000", "wcf-10000"])
@pytest.mark.parametrize("build", [Task.as_open, Task.as_closed, lambda task_id: Task(task_id, Status.OPEN)])
def test_valid_task_ids_are_kept_as_given(build, task_id: str) -> None:
    assert build(task_id).id == task_id


# U+212A, the Kelvin sign, lowercases to an ASCII k.
KELVIN = "\u212a"


@pytest.mark.parametrize(
    "task_id",
    [
        "WCF-0042",
        "Wcf-0042",
        "wcf-042",
        "wcf0042",
        "wcf-",
        "-0042",
        "w2-0042",
        "wcf_0042",
        "wcf-0042.lock",
        "fix-login.2",
        "t1",
        "7",
        f"{KELVIN}cf-0042",
        "",
        "wcf-0042\n",
        "wcf-\u0664\u0662\u0660\u0660",  # Arabic-Indic digits
    ],
)
@pytest.mark.parametrize("build", [Task.as_open, Task.as_closed, lambda task_id: Task(task_id, Status.OPEN)])
def test_task_ids_not_matching_the_pattern_are_refused_as_given(build, task_id: str) -> None:
    with pytest.raises(FoundryError) as error:
        build(task_id)
    assert str(error.value) == (
        f"task id {task_id!r} is not valid: use lowercase letters, '-', then four or more digits (e.g. wcf-0042)"
    )


# --- create ---------------------------------------------------------------------


def test_a_task_is_its_branch_from_the_default_branch_and_the_template_in_its_task_notes_dir(
    project_repository,
) -> None:
    notes_before = project_repository.head()

    assert create(project_repository) == Task.as_open("tst-0001")

    assert project_repository.head("task/tst-0001") == project_repository.head("main")
    assert project_repository.notes_files() == {
        ".agent/tasks/closed/cls-0000/TASK.md": "cls-0000\n",
        ".agent/tasks/open/tst-0000/TASK.md": "tst-0000\n",
        ".agent/tasks/open/tst-0001/PROGRESS.md": "# Progress\n",
        ".agent/tasks/open/tst-0001/TASK.md": "# Task <id>: <title>\n",
    }
    notes_parent = project_repository.git("rev-parse", f"{task.NOTES_BRANCH}^")
    assert notes_parent == notes_before


def test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files(project_repository) -> None:
    project_repository.git("branch", "--quiet", "-D", task.NOTES_BRANCH)

    create(project_repository)

    assert project_repository.notes_files() == {
        ".agent/tasks/open/tst-0001/PROGRESS.md": "# Progress\n",
        ".agent/tasks/open/tst-0001/TASK.md": "# Task <id>: <title>\n",
    }
    assert project_repository.git("rev-list", "--count", task.NOTES_BRANCH) == "1"


def test_the_tasks_notes_commit_is_signed_with_your_signing_key(project_repository) -> None:
    create(project_repository)

    assert project_repository.notes_signed_with_your_key()


def test_without_a_signing_key_nothing_is_pushed(project_repository, no_signing_key) -> None:
    notes_before = project_repository.head()

    with pytest.raises(
        GitError, match=r"(?s)^git -C \S+ commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"
    ):
        create(project_repository)
    assert project_repository.head() == notes_before
    assert "task/tst-0001" not in project_repository.git("branch", "--list")


def test_an_existing_task_branch_is_refused_and_nothing_is_written(project_repository) -> None:
    project_repository.git("branch", "task/tst-0001", "main")
    notes_before = project_repository.head()

    with pytest.raises(FoundryError, match=r"^task tst-0001 already exists: there is a task/tst-0001 branch$"):
        create(project_repository)
    assert project_repository.head() == notes_before


@pytest.mark.parametrize("task_id, found", [("tst-0000", "open/tst-0000"), ("cls-0000", "closed/cls-0000")])
def test_an_existing_task_notes_dir_open_or_closed_is_refused_and_nothing_is_pushed(
    project_repository, task_id: str, found: str
) -> None:
    notes_before = project_repository.head()
    with pytest.raises(FoundryError, match=rf"^task {task_id} already exists: agent-notes has .agent/tasks/{found}/$"):
        create(project_repository, task_id)
    assert f"task/{task_id}" not in project_repository.git("branch", "--list")
    assert project_repository.head() == notes_before


def test_a_closed_task_that_kept_its_branch_is_refused_naming_its_task_notes_dir(project_repository) -> None:
    project_repository.git("branch", "task/cls-0000", "main")

    with pytest.raises(
        FoundryError, match=r"^task cls-0000 already exists: agent-notes has .agent/tasks/closed/cls-0000/$"
    ):
        create(project_repository, "cls-0000")


def test_a_repository_with_no_commits_is_refused(tmp_path: Path, git_env) -> None:
    empty_dir = tmp_path / "empty.git"
    git(git_env, "init", "--quiet", "--bare", str(empty_dir))

    with pytest.raises(FoundryError, match=r"^the repository has no commits to branch task/tst-0001 from$"):
        project_tasks_of(empty_dir, git_env).create_task("tst-0001", TEMPLATE)


def test_an_unreachable_repository_fails_with_gits_message(tmp_path: Path, git_env) -> None:
    with pytest.raises(
        GitError, match=r"^git -C \S+ ls-remote --heads origin failed: .*does not appear to be a git repo"
    ):
        project_tasks_of(tmp_path / "missing.git", git_env).create_task("tst-0001", TEMPLATE)


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
        (
            CREATED,
            Task.as_open("tst-0001"),
            ["created task tst-0001 in store", "run it with: foundry run store tst-0001"],
        ),
        (
            CLOSED,
            Task.as_closed("tst-0001"),
            ["closed task tst-0001 in store", "reopen it with: foundry task reopen store tst-0001"],
        ),
        (
            REOPENED,
            Task.as_open("tst-0001"),
            ["reopened task tst-0001 in store", "run it with: foundry run store tst-0001"],
        ),
    ],
)
def test_the_report_says_what_was_done_and_what_comes_next(outcome: Outcome, changed: Task, lines: list[str]) -> None:
    assert report(outcome, "store", changed) == lines


def test_create_takes_a_project_and_a_task() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "tst-0001"])
    assert (args.project_name, args.task_id) == ("store", "tst-0001")


@pytest.mark.parametrize("action", ["close", "reopen"])
def test_close_and_reopen_take_a_project_and_a_task(action: str) -> None:
    args = cli.build_parser().parse_args(["task", action, "store", "tst-0001"])
    assert (args.project_name, args.task_id) == ("store", "tst-0001")


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


def test_write_refuses_a_link_and_writes_nothing_through_it(tmp_path: Path, git_env) -> None:
    work_dir = tmp_path / "clone"
    work_dir.mkdir()
    clone = ProjectClone.init(str(tmp_path / "origin.git"), work_dir, git_env)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n")
    (work_dir / "link.md").symlink_to(outside)

    with pytest.raises(FoundryError, match=r"^link\.md is a link: foundry writes only files$"):
        clone.write({"link.md": "2\n"})
    assert outside.read_text() == "outside\n"


# --- ProjectClone: fetch_branch, fetched_list_dir, fetched_read -------------------------


def test_fetch_branch_refuses_a_branch_the_remote_lacks(project_repository) -> None:
    clone = project_repository.clone()
    with pytest.raises(FoundryError, match=r"^the repository has no nope branch$"):
        clone.fetch_branch("nope")


def test_fetched_list_dir_lists_only_the_directories_in_a_fetched_branch(project_repository) -> None:
    clone = project_repository.fetched_clone()
    assert clone.fetched_list_dir(task.NOTES_BRANCH, task.OPEN_DIR) == ["tst-0000"]
    assert clone.fetched_list_dir(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000") == []  # TASK.md is a file


def test_fetched_list_dir_of_a_missing_dir_raises_the_narrow_error(project_repository) -> None:
    clone = project_repository.fetched_clone()
    with pytest.raises(NotOnBranchError):
        clone.fetched_list_dir(task.NOTES_BRANCH, ".agent/tasks/nope")
    with pytest.raises(NotOnBranchError):  # a file is not a dir
        clone.fetched_list_dir(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000/TASK.md")
    with pytest.raises(NotOnBranchError):  # a prefix of a dir's name is not that dir
        clone.fetched_list_dir(task.NOTES_BRANCH, task.OPEN_DIR[:-1])


def test_fetched_reads_of_an_unfetched_branch_raise_something_broader(project_repository) -> None:
    clone = project_repository.clone()
    for call in (
        lambda: clone.fetched_list_dir(task.NOTES_BRANCH, task.OPEN_DIR),
        lambda: clone.fetched_read(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000/TASK.md"),
    ):
        with pytest.raises(FoundryError, match=r"agent-notes isn't fetched") as raised:
            call()
        assert not isinstance(raised.value, NotOnBranchError)


def test_fetched_read_reads_a_file_and_a_link_as_its_target_name(project_repository) -> None:
    project_repository.edit_notes(symlink={".agent/tasks/open/tst-0000/LINK": "/etc/hostname"})

    clone = project_repository.fetched_clone()

    assert clone.fetched_read(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000/TASK.md") == "tst-0000\n"
    assert clone.fetched_read(task.NOTES_BRANCH, f"{task.OPEN_DIR}/tst-0000/LINK") == "/etc/hostname"


def test_fetched_read_of_a_missing_file_or_a_dir_raises_the_narrow_error(project_repository) -> None:
    clone = project_repository.fetched_clone()
    # "dir/" makes ls-tree list the dir's contents: still not a file
    for path in (f"{task.OPEN_DIR}/tst-0000/NOPE", f"{task.OPEN_DIR}/tst-0000", f"{task.OPEN_DIR}/tst-0000/"):
        with pytest.raises(NotOnBranchError):
            clone.fetched_read(task.NOTES_BRANCH, path)


# --- read_task_turn ---------------------------------------------------------------------


def turn_of(project_repository: ProjectRepository, task_id: str) -> str:
    return project_repository.project_tasks().read_task_turn(task_id)


def test_a_new_task_s_turn_is_the_template_s(project_repository) -> None:
    project_repository.project_tasks().create_task("tst-0001", {**TEMPLATE, "TURN": "dev\n"})

    assert turn_of(project_repository, "tst-0001") == "dev"


def test_a_task_without_a_turn_says_to_hand_it_off(project_repository) -> None:
    with pytest.raises(
        NoTurnError,
        match=r"^task tst-0000 has no turn: agent-notes has no \.agent/tasks/open/tst-0000/TURN, or it is empty\. "
        r"Hand it off with `foundry task turn store tst-0000 ROLE`\.$",
    ):
        turn_of(project_repository, "tst-0000")


def test_a_dir_at_turn_is_no_turn(project_repository) -> None:
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/TURN/dev": "dev\n"})

    with pytest.raises(
        FoundryError, match=r"^task tst-0000 has no turn: agent-notes has no .agent/tasks/open/tst-0000/TURN"
    ):
        turn_of(project_repository, "tst-0000")


def test_a_closed_task_s_turn_is_read_from_its_closed_task_notes_dir(project_repository) -> None:
    with pytest.raises(
        FoundryError, match=r"task cls-0000 has no turn: agent-notes has no .agent/tasks/closed/cls-0000/TURN"
    ):
        turn_of(project_repository, "cls-0000")


def test_a_task_that_doesn_t_exist_has_no_turn_to_read(project_repository) -> None:
    with pytest.raises(TaskNotFoundError):
        turn_of(project_repository, "tst-0009")


def test_the_task_template_starts_with_the_planner_s_turn() -> None:
    template = task.load_template(Path(__file__).parents[1] / "config" / "task-template")
    assert template[task.TURN_FILE].strip() == "planner"


# --- get_task_by_id ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "task_id, found", [("tst-0000", Task.as_open("tst-0000")), ("cls-0000", Task.as_closed("cls-0000"))]
)
def test_a_task_has_the_status_of_the_dir_holding_its_notes(project_repository, task_id: str, found) -> None:
    assert project_repository.project_tasks().get_task_by_id(task_id) == found


def test_a_task_in_neither_dir_is_not_found_naming_both(project_repository) -> None:
    with pytest.raises(
        TaskNotFoundError,
        match=(
            r"^task tst-0009 doesn't exist: "
            r"agent-notes has neither .agent/tasks/open/tst-0009/ nor .agent/tasks/closed/tst-0009/$"
        ),
    ):
        project_repository.project_tasks().get_task_by_id("tst-0009")


def test_a_repository_without_a_notes_branch_has_no_tasks(tmp_path: Path, git_env) -> None:
    bare_dir = tmp_path / "bare.git"
    git(git_env, "init", "--quiet", "--bare", str(bare_dir))
    with pytest.raises(TaskNotFoundError):
        project_tasks_of(bare_dir, git_env).get_task_by_id("tst-0001")


def test_a_task_in_both_dirs_is_refused_naming_both(project_repository) -> None:
    project_repository.edit_notes(write={".agent/tasks/closed/tst-0000/TASK.md": "tst-0000\n"})

    with pytest.raises(
        FoundryError, match=r"^task tst-0000 is both open and closed: .*open/tst-0000/ and .*closed/tst-0000/$"
    ) as error:
        project_repository.project_tasks().get_task_by_id("tst-0000")
    assert not isinstance(error.value, TaskNotFoundError)


# --- close_task, reopen_task -------------------------------------------------------------


def moved(files: dict[str, str], src: str, dst: str) -> dict[str, str]:
    """``files``, by path, with the ones under the notes dir ``src`` now under ``dst``."""
    return {
        dst + path.removeprefix(src) if path.startswith(f"{src}/") else path: entry for path, entry in files.items()
    }


def test_close_moves_the_task_notes_dir_unchanged_in_one_signed_commit(project_repository) -> None:
    project_repository.edit_notes(
        write={
            ".agent/tasks/open/tst-0000/sub/NOTE.md": "n\n",
            ".agent/tasks/open/tst-0000/PROGRESS.md": "p\n",
            ".agent/tasks/open/tst-00001/TASK.md": "tst-00001\n",
        },
    )
    before = project_repository.notes_files()
    commits_before = len(project_repository.notes_commits())
    branches_before = project_repository.git("branch", "--list")

    assert project_repository.project_tasks().close_task("tst-0000") == Task.as_closed("tst-0000")

    expected = moved(before, ".agent/tasks/open/tst-0000", ".agent/tasks/closed/tst-0000")
    assert project_repository.notes_files() == expected
    assert ".agent/tasks/closed/tst-0000/sub/NOTE.md" in expected
    assert ".agent/tasks/open/tst-00001/TASK.md" in expected
    assert project_repository.notes_commits()[0] == "Close task tst-0000"
    assert len(project_repository.notes_commits()) == commits_before + 1
    assert project_repository.notes_signed_with_your_key()
    assert project_repository.git("branch", "--list") == branches_before


def test_reopen_makes_the_reverse_move_in_one_signed_commit(project_repository) -> None:
    before = project_repository.notes_files()

    assert project_repository.project_tasks().reopen_task("cls-0000") == Task.as_open("cls-0000")

    expected = moved(before, ".agent/tasks/closed/cls-0000", ".agent/tasks/open/cls-0000")
    assert project_repository.notes_files() == expected
    assert project_repository.notes_commits()[0] == "Reopen task cls-0000"
    assert project_repository.notes_signed_with_your_key()


def test_a_move_keeps_files_your_git_config_would_ignore_or_convert(project_repository, git_env) -> None:
    project_repository.edit_notes(
        write={".agent/tasks/open/tst-0000/run.log": "log\n", ".agent/tasks/open/tst-0000/crlf.md": "a\r\nb\r\n"},
    )
    home_dir = Path(git_env["HOME"])
    (home_dir / "excludes").write_text("*.log\n")
    with (home_dir / ".gitconfig").open("a") as gitconfig:
        gitconfig.write(f"[core]\n\texcludesFile = {home_dir / 'excludes'}\n\tautocrlf = input\n")
    before = project_repository.notes_tree()

    project_repository.project_tasks().close_task("tst-0000")

    assert project_repository.notes_tree() == moved(
        before, ".agent/tasks/open/tst-0000", ".agent/tasks/closed/tst-0000"
    )


@pytest.mark.parametrize(
    "operation, task_id, message",
    [
        (ProjectTasks.close_task, "cls-0000", "^task cls-0000 is already closed$"),
        (ProjectTasks.close_task, "tst-0009", r"^task tst-0009 doesn't exist: "),
        (ProjectTasks.reopen_task, "tst-0000", "^task tst-0000 is already open$"),
        (ProjectTasks.reopen_task, "tst-0009", r"^task tst-0009 doesn't exist: "),
    ],
)
def test_close_and_reopen_refuse_and_push_nothing(project_repository, operation, task_id, message) -> None:
    notes_before = project_repository.head()

    with pytest.raises(FoundryError, match=message):
        operation(project_repository.project_tasks(), task_id)
    assert project_repository.head() == notes_before


@pytest.mark.parametrize(
    "operation, task_id",
    [(ProjectTasks.close_task, "tst-0000"), (ProjectTasks.reopen_task, "cls-0000")],
    ids=["close", "reopen"],
)
def test_without_a_signing_key_close_and_reopen_push_nothing(
    project_repository, no_signing_key, operation, task_id
) -> None:
    notes_before = project_repository.head()

    with pytest.raises(GitError, match=r"(?s)commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"):
        operation(project_repository.project_tasks(), task_id)
    assert project_repository.head() == notes_before


# --- log_with_turn_entry -----------------------------------------------------------------


@pytest.mark.parametrize(
    "log, note, expected",
    [
        ("", None, "## 1 · human · turn\nTurn: none → dev.\n"),
        (" \n\n", None, "## 1 · human · turn\nTurn: none → dev.\n"),
        ("# Log\n", None, "# Log\n\n## 1 · human · turn\nTurn: none → dev.\n"),
        ("# Log\n\n\n \t\n", None, "# Log\n\n## 1 · human · turn\nTurn: none → dev.\n"),
        (
            "# Log\n\n## 1 · planner · planned\nDone.\n\n## 2 · dev · progress\nDone.\n",
            "  look at R3  ",
            "# Log\n\n## 1 · planner · planned\nDone.\n\n## 2 · dev · progress\nDone.\n"
            "\n## 3 · human · turn\nTurn: none → dev.\nNote: look at R3\n",
        ),
        (
            "# Log\n\n## 12 · dev · progress\n\n## 4 · reviewer · changes-needed\nSee REVIEW.md.",
            None,
            "# Log\n\n## 12 · dev · progress\n\n## 4 · reviewer · changes-needed\nSee REVIEW.md.\n"
            "\n## 5 · human · turn\nTurn: none → dev.\n",
        ),
        (
            "# Log\n\n## 7 · dev · progress\n  ## 9 · dev · indented\n## 10 · \n## 11 · x\n## x · dev\n",
            None,
            "# Log\n\n## 7 · dev · progress\n  ## 9 · dev · indented\n## 10 · \n## 11 · x\n## x · dev\n"
            "\n## 12 · human · turn\nTurn: none → dev.\n",
        ),
    ],
    ids=[
        "empty",
        "blank",
        "no-entries",
        "trailing-blank-lines",
        "entries-with-note",
        "last-heading-not-highest-no-final-newline",
        "headings-only",
    ],
)
def test_the_turn_entry_follows_the_log_after_one_blank_line_numbered_after_its_last_entry(log, note, expected) -> None:
    """The log's text is kept, but for the whitespace at its end."""
    assert log_with_turn_entry(log, before="none", after="dev", note=note) == expected


def test_the_turn_entry_names_both_turns() -> None:
    assert log_with_turn_entry("# Log\n", before="reviewer", after="human", note=None).endswith(
        "\n\n## 1 · human · turn\nTurn: reviewer → human.\n"
    )


# --- handoff ------------------------------------------------------------------------------

LOG = "# Log\n\n## 1 · planner · planned\nDone.\n"


def handoff(project_repository: ProjectRepository, task_id: str, *, note: str | None = None) -> str:
    """Hand ``task_id`` off to dev, through a clone of its own; the turn before."""
    return project_repository.project_tasks().handoff(task_id, "dev", note=note)


@pytest.mark.parametrize(
    "turn_files, before",
    [
        ({".agent/tasks/open/tst-0000/TURN": " reviewer \n"}, "reviewer"),
        ({}, "none"),
        ({".agent/tasks/open/tst-0000/TURN": " \n\t"}, "none"),
    ],
    ids=["a-turn", "no-turn", "blank-turn"],
)
def test_handoff_writes_turn_and_appends_to_the_log_in_one_signed_commit(
    project_repository, turn_files, before
) -> None:
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/LOG.md": LOG, **turn_files})
    files_before = project_repository.notes_files()
    commits_before = len(project_repository.notes_commits())

    assert handoff(project_repository, "tst-0000", note=" see R2 ") == before
    expected_log = LOG + f"\n## 2 · human · turn\nTurn: {before} → dev.\nNote: see R2\n"
    assert project_repository.notes_files() == {
        **files_before,
        ".agent/tasks/open/tst-0000/TURN": "dev\n",
        ".agent/tasks/open/tst-0000/LOG.md": expected_log,
    }
    assert project_repository.notes_commits()[0] == f"Turn of task tst-0000: {before} → dev"
    assert len(project_repository.notes_commits()) == commits_before + 1
    assert project_repository.notes_signed_with_your_key()


@pytest.mark.parametrize(
    "task_id, edits, message",
    [
        ("tst-0009", {}, r"^task tst-0009 doesn't exist: "),
        ("cls-0000", {}, r"^task cls-0000 is closed: reopen it with `foundry task reopen store cls-0000`$"),
        (
            "tst-0000",
            {"write": {".agent/tasks/open/tst-0000/TURN": "dev\n", ".agent/tasks/open/tst-0000/LOG.md": LOG}},
            r"^task tst-0000's turn is already dev$",
        ),
        (
            "tst-0000",
            {},
            r"^task tst-0000 has no LOG\.md: agent-notes has no file \.agent/tasks/open/tst-0000/LOG\.md$",
        ),
        (
            "tst-0000",
            {"write": {".agent/tasks/open/tst-0000/LOG.md/x": "x\n"}},
            r"^task tst-0000 has no LOG\.md: agent-notes has no file \.agent/tasks/open/tst-0000/LOG\.md$",
        ),
        (
            "tst-0000",
            {"write": {".agent/LOG.md": LOG}, "symlink": {".agent/tasks/open/tst-0000/LOG.md": "../../../LOG.md"}},
            r"^\.agent/tasks/open/tst-0000/LOG\.md is a link: foundry writes only files$",
        ),
    ],
    ids=["not-found", "closed", "same-turn", "no-log", "log-is-a-dir", "log-is-a-link"],
)
def test_handoff_refuses_and_pushes_nothing(project_repository, task_id, edits, message) -> None:
    if edits:
        project_repository.edit_notes(**edits)
    notes_before = project_repository.head()

    with pytest.raises(FoundryError, match=message):
        handoff(project_repository, task_id)
    assert project_repository.head() == notes_before


def test_without_a_signing_key_handoff_pushes_nothing(project_repository, no_signing_key) -> None:
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/LOG.md": LOG})
    notes_before = project_repository.head()

    with pytest.raises(GitError, match=r"(?s)commit --quiet --message .* failed: .*user\.signingkey.*ssh-add -L"):
        handoff(project_repository, "tst-0000")
    assert project_repository.head() == notes_before


# --- list_open_task_summaries -----------------------------------------------------------


def summaries_of(project_tasks: ProjectTasks) -> list[tuple[str, str]]:
    found = project_tasks.list_open_task_summaries()
    assert all(summary.task.status is Status.OPEN for summary in found)
    return [(summary.task.id, summary.turn) for summary in found]


def test_open_tasks_are_listed_in_id_order_with_their_stripped_turns(project_repository) -> None:
    project_repository.edit_notes(
        write={
            ".agent/tasks/open/tst-0000/TURN": "dev\n",
            ".agent/tasks/open/bbb-0001/TURN": "  human \n\n",
            ".agent/tasks/open/aaa-0002/TURN": "reviewer",
            ".agent/tasks/closed/cls-0000/TURN": "dev\n",  # closed: left out
            ".agent/tasks/open/stray.txt": "not a task\n",  # a file: ignored
        },
    )

    assert summaries_of(project_repository.project_tasks()) == [
        ("aaa-0002", "reviewer"),
        ("bbb-0001", "human"),
        ("tst-0000", "dev"),
    ]
    assert isinstance(project_repository.project_tasks().list_open_task_summaries()[0], TaskSummary)


def test_a_symlinked_turn_shows_the_link_s_target_name_and_reads_nothing_outside(project_repository) -> None:
    project_repository.edit_notes(symlink={".agent/tasks/open/tst-0000/TURN": "/etc/hostname"})

    assert summaries_of(project_repository.project_tasks()) == [("tst-0000", "/etc/hostname")]


def test_no_open_dir_after_the_last_task_closed_lists_nothing(project_repository) -> None:
    project_repository.edit_notes(remove=[".agent/tasks/open"])

    assert summaries_of(project_repository.project_tasks()) == []


@pytest.mark.parametrize(
    "files",
    [{}, {".agent/tasks/open/tst-0000/TURN": " \n"}, {".agent/tasks/open/tst-0000/TURN/x": "x"}],
    ids=["missing", "empty", "directory"],
)
def test_a_missing_empty_or_directory_turn_fails_naming_the_task(project_repository, files) -> None:
    if files:  # tst-0000 starts without a TURN
        project_repository.edit_notes(write=files)

    with pytest.raises(
        FoundryError,
        match=r"^task tst-0000 has no turn: agent-notes has no .*TURN.*`foundry task turn store tst-0000 ROLE`\.$",
    ):
        summaries_of(project_repository.project_tasks())


def test_a_dir_that_is_not_a_task_id_fails_naming_it(project_repository) -> None:
    project_repository.edit_notes(
        write={".agent/tasks/open/tst-0000/TURN": "dev\n", ".agent/tasks/open/Bad Dir/TURN": "dev"}
    )

    with pytest.raises(
        FoundryError,
        match=r"^.agent/tasks/open/Bad Dir/ is not a valid task id \(task id 'Bad Dir' is not valid: "
        r"use lowercase letters, .*\)\. Rename or remove it\.$",
    ):
        summaries_of(project_repository.project_tasks())


def test_listing_a_repository_without_a_notes_branch_names_agent_notes(tmp_path: Path, git_env) -> None:
    bare_dir = tmp_path / "bare.git"
    git(git_env, "init", "--quiet", "--bare", str(bare_dir))

    with pytest.raises(FoundryError, match=r"^the repository has no agent-notes branch$"):
        summaries_of(project_tasks_of(bare_dir, git_env))


def test_listing_an_unreachable_repository_fails_with_gits_message(tmp_path: Path, git_env) -> None:
    with pytest.raises(GitError, match=r"ls-remote --heads origin failed: .*does not appear to be a git repo"):
        summaries_of(project_tasks_of(tmp_path / "missing.git", git_env))


def test_listing_costs_one_fetch_however_many_tasks(project_repository, git_env, tmp_path: Path) -> None:
    project_repository.edit_notes(write={f".agent/tasks/open/tst-{n:04}/TURN": "dev\n" for n in range(0, 6)})
    log = tmp_path / "git-calls.log"
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    real_git = subprocess.run(["which", "git"], env=git_env, capture_output=True, text=True, check=True).stdout.strip()
    shim = shim_dir / "git"
    shim.write_text(f'#!/bin/sh\necho "$*" >> {log}\nexec {real_git} "$@"\n')
    shim.chmod(0o755)
    counting_env = {**git_env, "PATH": f"{shim_dir}:{git_env['PATH']}"}

    found = project_repository.project_tasks(env=counting_env).list_open_task_summaries()

    assert len(found) == 6
    assert sum(" fetch " in f" {line} " for line in log.read_text().splitlines()) == 1


# --- foundry task list: the lines and the arguments -----------------------------------------


def listing(name: str, *turns: tuple[str, str]) -> ProjectListing:
    return ProjectListing(name, [TaskSummary(Task.as_open(task_id), turn) for task_id, turn in turns])


def test_task_lines_are_aligned_across_every_project_with_two_spaces_between_columns() -> None:
    stdout, stderr = listing_lines(
        [listing("store", ("wcf-0007", "dev"), ("wcf-0010", "human")), listing("a", ("t-0001", "reviewer"))],
        [],
    )

    assert stdout == [
        "store  wcf-0007  dev",
        "store  wcf-0010  human",
        "a      t-0001    reviewer",
    ]
    assert stderr == []


def test_turn_keeps_only_the_tasks_whose_turn_is_exactly_that() -> None:
    store = listing("store", ("tst-0001", "dev"), ("tst-0002", "developer"), ("tst-0003", "dev"), ("tst-0004", "Dev"))

    kept = filter_project_listing(store, "dev")

    assert kept.project_name == "store"
    assert kept.summaries == listing("store", ("tst-0001", "dev"), ("tst-0003", "dev")).summaries
    assert len(store.summaries) == 4  # a new listing; the one given is left as it was


def test_no_turn_keeps_the_listing_as_it_is() -> None:
    store = listing("store", ("tst-0001", "dev"))

    assert filter_project_listing(store, None) is store


def test_a_project_without_tasks_is_a_line_outside_the_columns() -> None:
    stdout, _ = listing_lines([listing("empty-and-long"), listing("store", ("wcf-0007", "dev"))], [])

    assert stdout == ["empty-and-long  no open tasks", "store  wcf-0007  dev"]  # its name doesn't widen the column


def test_turn_with_open_tasks_but_none_matching_says_so() -> None:
    stdout, _ = listing_lines(
        [
            filter_project_listing(listing("store", ("tst-0001", "dev")), "human"),
            filter_project_listing(listing("empty"), "human"),
        ],
        [],
    )

    assert stdout == ["store  no open tasks with turn human", "empty  no open tasks"]


def test_a_failed_project_is_an_error_line_and_the_others_are_still_listed() -> None:
    stdout, stderr = listing_lines([listing("store", ("tst-0001", "dev"))], [FoundryError("bad: boom")])

    assert (stdout, stderr) == (["store  tst-0001  dev"], ["error: bad: boom"])


def test_list_takes_optional_projects_and_a_turn() -> None:
    parse = cli.build_parser().parse_args
    assert (parse(["task", "list"]).project_names, parse(["task", "list"]).turn) == ([], None)
    args = parse(["task", "list", "store", "blog", "--turn", "human"])
    assert (args.project_names, args.turn) == (["store", "blog"], "human")


def test_chosen_projects_are_in_name_order_once_each_and_all_when_none_are_named() -> None:
    foundry_config = Config("f", {name: Project(name, f"url/{name}") for name in ("store", "blog")}, {})

    assert [p.name for p in chosen_projects(foundry_config, [])] == ["blog", "store"]
    assert [p.name for p in chosen_projects(foundry_config, ["store", "blog", "store"])] == ["blog", "store"]


def test_an_unknown_project_is_refused_as_create_refuses_it() -> None:
    foundry_config = Config("f", {"store": Project("store", "url")}, {})

    with pytest.raises(FoundryError, match=r"^unknown project 'nope'; known: store$"):
        chosen_projects(foundry_config, ["store", "nope"])


def test_each_project_gives_a_listing_or_an_error_naming_it(project_repository, git_env, tmp_path: Path) -> None:
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/TURN": "dev\n"})
    git(git_env, "init", "--quiet", "--bare", str(tmp_path / "bare.git"))  # no agent-notes: a FoundryError
    projects = [
        Project("bare", str(tmp_path / "bare.git")),
        Project("gone", str(tmp_path / "missing.git")),  # unreachable: git's GitError
        Project("store", str(project_repository.path)),
    ]

    listings, errors = read_listings_and_errors(projects, git_env)

    assert listings == [ProjectListing("store", [TaskSummary(Task.as_open("tst-0000"), "dev")])]
    assert [type(error) for error in errors] == [FoundryError, FoundryError]
    assert str(errors[0]) == "bare: the repository has no agent-notes branch"
    assert str(errors[1]).startswith("gone: ") and "does not appear to be a git repo" in str(errors[1])


def test_list_prints_tasks_on_stdout_errors_on_stderr_and_exits_1_if_a_project_failed(
    project_repository, git_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, in a foundry instance of its own: one project lists, the other can't be reached."""
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/TURN": "dev\n"})
    foundry_root = tmp_path / "foundry"
    (foundry_root / "config").mkdir(parents=True)
    (foundry_root / "config" / "foundry.yaml").write_text(
        f"name: f\nprojects:\n  store: {{url: '{project_repository.path}'}}\n"
        f"  gone: {{url: '{tmp_path / 'missing.git'}'}}\n"
        "roles: {}\n"
    )
    monkeypatch.chdir(foundry_root)
    for name, value in git_env.items():
        monkeypatch.setenv(name, value)

    assert cli.main(["task", "list"]) == 1
    printed = capsys.readouterr()
    assert printed.out == "store  tst-0000  dev\n"
    assert printed.err.startswith("error: gone: ") and printed.err.count("error: ") == 1

    assert cli.main(["task", "list", "store"]) == 0
    assert capsys.readouterr() == ("store  tst-0000  dev\n", "")

    assert cli.main(["task", "list", "store", "--turn", "human"]) == 0
    assert capsys.readouterr() == ("store  no open tasks with turn human\n", "")


# --- foundry task turn ------------------------------------------------------------------

TURN_CONFIG = Config(
    "f",
    {"store": Project("store", "url")},
    {name: Role(name, Path(f"/secrets/ssh/{name}"), None) for name in ("reviewer", "dev")},
)


@pytest.mark.parametrize("turn", ["dev", "human"])
@pytest.mark.parametrize("note", [None, "see R2", "  padded  "])
def test_handoff_args_that_check_out_pass(turn: str, note: str | None) -> None:
    require_valid_handoff_args(TURN_CONFIG, task_id="tst-0001", turn=turn, note=note)


@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"turn": "dve"}, r"^'dve' is not a role; known: dev, reviewer, or human$"),
        ({"turn": "Human"}, r"^'Human' is not a role; known: dev, reviewer, or human$"),
        ({"turn": ""}, r"^'' is not a role; known: dev, reviewer, or human$"),
        ({"note": ""}, r"^--note is empty: give it text, or leave it out$"),
        ({"note": " \t "}, r"^--note is empty: give it text, or leave it out$"),
        ({"note": "one\ntwo"}, r"^--note holds a line break: give it one line$"),
        ({"note": "one\r"}, r"^--note holds a line break: give it one line$"),
        ({"note": "one\u2028two"}, r"^--note holds a line break: give it one line$"),
        ({"task_id": "TST-0001"}, r"^task id 'TST-0001' is not valid: "),
    ],
    ids=[
        "unknown-role",
        "human-capitalised",
        "empty-role",
        "empty-note",
        "blank-note",
        "note-newline",
        "note-return",
        "note-line-separator",
        "invalid-task-id",
    ],
)
def test_handoff_args_are_refused_before_any_git(arguments, message) -> None:
    valid = {"task_id": "tst-0001", "turn": "dev", "note": None}
    with pytest.raises(FoundryError, match=message):
        require_valid_handoff_args(TURN_CONFIG, **{**valid, **arguments})


def test_a_config_without_roles_knows_only_human() -> None:
    with pytest.raises(FoundryError, match=r"^'dev' is not a role; known: none, or human$"):
        require_valid_handoff_args(
            Config("f", {"store": Project("store", "url")}, {}), task_id="tst-0001", turn="dev", note=None
        )


@pytest.mark.parametrize(
    "after, lines",
    [
        ("dev", ["task tst-0001 in store: turn none → dev", "run it with: foundry run store tst-0001"]),
        ("human", ["task tst-0001 in store: turn none → human"]),
    ],
)
def test_the_handoff_lines_say_how_to_run_the_task_unless_it_waits_for_you(after: str, lines: list[str]) -> None:
    assert handoff_lines("store", "tst-0001", before="none", after=after) == lines


def test_turn_takes_a_project_a_task_a_role_and_an_optional_note() -> None:
    args = cli.build_parser().parse_args(["task", "turn", "store", "tst-0001", "dev", "--note", "see R2"])
    assert (args.project_name, args.task_id, args.turn, args.note) == ("store", "tst-0001", "dev", "see R2")
    assert cli.build_parser().parse_args(["task", "turn", "store", "tst-0001", "human"]).note is None


def test_turn_prints_the_handoff_or_an_error_and_exits_accordingly(
    project_repository, git_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, in a foundry instance of its own with one role, dev."""
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/LOG.md": "# Log\n"})
    foundry_root = tmp_path / "foundry"
    (foundry_root / "config").mkdir(parents=True)
    (foundry_root / "config" / "foundry.yaml").write_text(
        f"name: f\nprojects:\n  store: {{url: '{project_repository.path}'}}\nroles:\n  dev: {{}}\n"
    )
    role_dir = foundry_root / "agent-kit" / "roles" / "dev"
    role_dir.mkdir(parents=True)
    (role_dir / "ROLE.md").write_text("dev\n")
    (role_dir / "gitconfig").write_text("")
    monkeypatch.chdir(foundry_root)
    for name, value in git_env.items():
        monkeypatch.setenv(name, value)

    assert cli.main(["task", "turn", "store", "tst-0000", "dev", "--note", "go"]) == 0
    assert capsys.readouterr() == (
        "task tst-0000 in store: turn none → dev\nrun it with: foundry run store tst-0000\n",
        "",
    )
    assert project_repository.notes_commits()[0] == "Turn of task tst-0000: none → dev"

    notes_before = project_repository.head()
    assert cli.main(["task", "turn", "store", "tst-0000", "dev"]) == 1
    assert capsys.readouterr() == ("", "error: task tst-0000's turn is already dev\n")
    assert cli.main(["task", "turn", "store", "tst-0000", "planner"]) == 1
    assert capsys.readouterr() == ("", "error: 'planner' is not a role; known: dev, or human\n")
    assert cli.main(["task", "turn", "nope", "tst-0000", "dev"]) == 1
    assert capsys.readouterr() == ("", "error: unknown project 'nope'; known: store\n")
    assert project_repository.head() == notes_before

    assert cli.main(["task", "turn", "store", "tst-0000", "human"]) == 0
    assert capsys.readouterr() == ("task tst-0000 in store: turn dev → human\n", "")


# --- an id given in uppercase ------------------------------------------------------------


@pytest.mark.parametrize(
    "operation, task_id",
    [
        (ProjectTasks.create_task, "TST-0001"),
        (ProjectTasks.create_task, "TST-0000"),
        (ProjectTasks.close_task, "TST-0000"),
        (ProjectTasks.reopen_task, "CLS-0000"),
        (ProjectTasks.get_task_by_id, "TST-0000"),
    ],
    ids=["create", "create-existing", "close", "reopen", "get"],
)
def test_an_uppercase_id_is_refused_not_lowercased_and_nothing_is_pushed(
    project_repository, operation, task_id: str
) -> None:
    project_tasks = project_repository.project_tasks()
    args = (task_id, TEMPLATE) if operation is ProjectTasks.create_task else (task_id,)
    refs_before = project_repository.git("for-each-ref")

    with pytest.raises(FoundryError, match=rf"^task id '{task_id}' is not valid: ") as error:
        operation(project_tasks, *args)
    assert not isinstance(error.value, TaskNotFoundError)
    assert project_repository.git("for-each-ref") == refs_before
