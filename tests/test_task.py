"""foundry/task.py and the `foundry task` commands' git, against a real repository on disk: creating a task, reading
its task state, listing tasks and moving one by hand; and the commands' reports and arguments."""

import os
import re
import subprocess
from pathlib import Path

import pytest

from agent_runtime.git import GitError
from agent_runtime.task.lifecycles import BUGFIX, FEATURE, Lifecycle
from agent_runtime.task.state import TaskState
from foundry import cli, task
from foundry.commands.task import Row, move_task, read_rows, report, table
from foundry.errors import FoundryError
from foundry.project_clone import ProjectClone
from foundry.task import Task

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


def scratch_clone(origin_dir: Path, git_env: dict[str, str], name: str) -> ProjectClone:
    scratch_dir = origin_dir.parent / f"scratch-{name}"
    scratch_dir.mkdir()
    return ProjectClone.init(str(origin_dir), scratch_dir, git_env)


def create(origin_dir: Path, git_env: dict[str, str], task_id: str = "T1", lifecycle: Lifecycle = FEATURE) -> None:
    task.create(scratch_clone(origin_dir, git_env, task_id), Task(task_id), TEMPLATE, lifecycle)


def branch_files(origin_dir: Path, git_env: dict[str, str], branch: str) -> dict[str, str]:
    paths = git(git_env, f"--git-dir={origin_dir}", "ls-tree", "-r", "--name-only", branch).splitlines()
    return {path: git(git_env, f"--git-dir={origin_dir}", "show", f"{branch}:{path}") + "\n" for path in paths}


def head(origin_dir: Path, git_env: dict[str, str], branch: str) -> str:
    return git(git_env, f"--git-dir={origin_dir}", "rev-parse", f"refs/heads/{branch}")


# --- Task -----------------------------------------------------------------------


def test_a_task_is_its_lowercased_id_its_branch_and_its_notes_folder() -> None:
    a_task = Task("WCF-0042")
    assert (a_task.id, a_task.branch, a_task.task_notes_dir, a_task.task_file) == (
        "wcf-0042",
        "task/wcf-0042",
        ".agent/wcf-0042",
        ".agent/wcf-0042/TASK.md",
    )
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
    assert branch_files(origin_dir, git_env, task.NOTES_BRANCH) == {
        ".agent/t0/TASK.md": "an earlier task\n",
        ".agent/t1/PROGRESS.md": "# Progress\n",
        ".agent/t1/STATE.json": TaskState.new(FEATURE).to_json(),
        ".agent/t1/TASK.md": "# Task <id>: <title>\n",
    }
    notes_parent = git(git_env, f"--git-dir={origin_dir}", "rev-parse", f"{task.NOTES_BRANCH}^")
    assert notes_parent == notes_before


def test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files(origin_dir, git_env) -> None:
    git(git_env, f"--git-dir={origin_dir}", "branch", "--quiet", "-D", task.NOTES_BRANCH)

    create(origin_dir, git_env)

    assert branch_files(origin_dir, git_env, task.NOTES_BRANCH) == {
        ".agent/t1/PROGRESS.md": "# Progress\n",
        ".agent/t1/STATE.json": TaskState.new(FEATURE).to_json(),
        ".agent/t1/TASK.md": "# Task <id>: <title>\n",
    }
    assert git(git_env, f"--git-dir={origin_dir}", "rev-list", "--count", task.NOTES_BRANCH) == "1"


def test_the_tasks_notes_commit_is_signed_with_your_signing_key(origin_dir, git_env) -> None:
    create(origin_dir, git_env)

    commit = git(git_env, f"--git-dir={origin_dir}", "cat-file", "commit", task.NOTES_BRANCH)
    assert f"gpgsig -----BEGIN SSH SIGNATURE-----\n {SIGNING_KEY}\n" in commit


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
    with pytest.raises(
        GitError, match=r"^git -C \S+ ls-remote --symref origin HEAD failed: .*does not appear to be a git repo"
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


def test_the_report_says_what_was_created_and_how_to_run_it() -> None:
    assert report("store", Task("T1")) == ["created task t1 in store", "run it with: foundry task run store t1"]


def test_create_takes_a_project_and_a_task_and_a_lifecycle_defaulting_to_feature() -> None:
    args = cli.build_parser().parse_args(["task", "create", "store", "T1"])
    assert (args.project_name, args.task_id, args.lifecycle) == ("store", "T1", "feature")
    assert (
        cli.build_parser().parse_args(["task", "create", "store", "T1", "--lifecycle", "bugfix"]).lifecycle == "bugfix"
    )


def test_an_unknown_lifecycle_is_refused_before_anything_runs(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["task", "create", "store", "T1", "--lifecycle", "epic"])
    assert "argument --lifecycle: invalid choice: 'epic'" in capsys.readouterr().err


def test_move_takes_a_state_and_requires_a_note(capsys: pytest.CaptureFixture[str]) -> None:
    args = cli.build_parser().parse_args(["task", "move", "store", "T1", "review", "--note", "Answered."])
    assert (args.project_name, args.task_id, args.state, args.note) == ("store", "T1", "review", "Answered.")
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["task", "move", "store", "T1", "review"])
    assert "--note" in capsys.readouterr().err


def test_run_takes_no_role() -> None:
    args = cli.build_parser().parse_args(["task", "run", "store", "T1"])
    assert (args.project_name, args.task_id) == ("store", "T1")


def test_there_is_no_foundry_run(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["run", "store", "dev", "T1"])
    assert "invalid choice: 'run'" in capsys.readouterr().err


# --- ProjectClone: what task.create can't reach ---------------------------------------


def test_a_push_of_no_branches_is_refused(tmp_path: Path, git_env) -> None:
    clone_dir = tmp_path / "clone"  # ProjectClone.init needs an empty folder; tmp_path holds git_env's home/
    clone_dir.mkdir()
    clone = ProjectClone.init(str(tmp_path / "origin.git"), clone_dir, git_env)
    with pytest.raises(AssertionError, match="at least one branch"):
        clone.push_atomic(from_remote={}, from_local=[])


# --- task states -------------------------------------------------------------------


def test_a_task_chooses_its_lifecycle(origin_dir, git_env) -> None:
    create(origin_dir, git_env, lifecycle=BUGFIX)

    files = branch_files(origin_dir, git_env, task.NOTES_BRANCH)
    assert TaskState.parse(files[".agent/t1/STATE.json"], "STATE.json") == TaskState.new(BUGFIX)


def notes_clone(origin_dir: Path, git_env: dict[str, str], name: str) -> ProjectClone:
    clone = scratch_clone(origin_dir, git_env, name)
    clone.check_out(task.NOTES_BRANCH)
    return clone


def test_a_tasks_state_is_read_from_the_notes_branch(origin_dir, git_env) -> None:
    create(origin_dir, git_env)

    assert task.read_state(notes_clone(origin_dir, git_env, "read"), Task("T1")) == TaskState.new(FEATURE)


def test_reading_a_task_that_doesnt_exist_is_refused(origin_dir, git_env) -> None:
    with pytest.raises(FoundryError, match=r"^there is no task t9\. agent-notes has no \.agent/t9/\.$"):
        task.read_state(notes_clone(origin_dir, git_env, "read"), Task("T9"))


def test_a_task_created_before_task_states_is_refused(origin_dir, git_env) -> None:
    with pytest.raises(FoundryError) as refused:
        task.read_state(notes_clone(origin_dir, git_env, "read"), Task("T0"))

    assert (
        str(refused.value) == "task t0 has no .agent/t0/STATE.json on agent-notes. It was created before task states."
    )


def test_a_move_by_hand_commits_the_task_state_signed_and_pushes_the_notes_branch_alone(origin_dir, git_env) -> None:
    create(origin_dir, git_env)
    task_branch = head(origin_dir, git_env, "task/t1")

    old, moved = move_task(
        scratch_clone(origin_dir, git_env, "move"), Task("T1"), to="implement", note="Write it yourself."
    )

    assert (old.state, moved.state) == ("plan", "implement")
    files = branch_files(origin_dir, git_env, task.NOTES_BRANCH)
    assert TaskState.parse(files[".agent/t1/STATE.json"], "STATE.json") == TaskState(
        lifecycle=FEATURE, state="implement", note="Write it yourself."
    )
    commit = git(git_env, f"--git-dir={origin_dir}", "cat-file", "commit", task.NOTES_BRANCH)
    assert "t1: plan → implement (moved by hand)" in commit and "gpgsig -----BEGIN SSH SIGNATURE-----" in commit
    assert head(origin_dir, git_env, "task/t1") == task_branch


@pytest.mark.parametrize(
    ("to", "note", "message"), [("draft", "x", "feature has no state 'draft'"), ("review", " ", "Give a hand-off note")]
)
def test_a_refused_move_pushes_nothing(origin_dir, git_env, to: str, note: str, message: str) -> None:
    create(origin_dir, git_env)
    notes_before = head(origin_dir, git_env, task.NOTES_BRANCH)

    with pytest.raises(Exception, match=message):
        move_task(scratch_clone(origin_dir, git_env, "move"), Task("T1"), to=to, note=note)
    assert head(origin_dir, git_env, task.NOTES_BRANCH) == notes_before


def test_list_has_a_row_per_readable_task_and_the_whole_error_for_each_other(origin_dir, git_env) -> None:
    create(origin_dir, git_env)

    rows, errors = read_rows("store", scratch_clone(origin_dir, git_env, "list"))

    assert [(row.task.id, row.task_state) for row in rows] == [("t1", TaskState.new(FEATURE))]
    assert (
        errors[0] == "store t0: task t0 has no .agent/t0/STATE.json on agent-notes. It was created before task states."
    )
    assert len(errors) == 1


def test_a_bad_task_id_or_a_state_that_isnt_a_text_file_is_that_tasks_own_error(origin_dir, git_env, tmp_path) -> None:
    """Round 4's R51 and R52, and a STATE.json that is a folder or a link: none stops the list, and a link is
    never followed out of the clone."""
    create(origin_dir, git_env)
    notes_dir = tmp_path / "notes"
    git(git_env, "clone", "--quiet", "--branch", task.NOTES_BRANCH, str(origin_dir), str(notes_dir))
    (notes_dir / ".agent" / "Old Notes").mkdir()
    (notes_dir / ".agent" / "Old Notes" / "TASK.md").write_text("old\n")
    (notes_dir / ".agent" / "t2").mkdir()
    (notes_dir / ".agent" / "t2" / "STATE.json").write_bytes(b"\xff\xfe")
    (notes_dir / ".agent" / "t3" / "STATE.json").mkdir(parents=True)
    (notes_dir / ".agent" / "t3" / "STATE.json" / "x").write_text("x\n")
    (notes_dir / ".agent" / "t4").mkdir()
    (notes_dir / ".agent" / "t4" / "STATE.json").symlink_to("/etc/hostname")
    git(git_env, "-C", str(notes_dir), "add", ".agent")
    git(git_env, "-C", str(notes_dir), "commit", "--quiet", "--no-gpg-sign", "-m", "odd tasks")
    git(git_env, "-C", str(notes_dir), "push", "--quiet", "origin", task.NOTES_BRANCH)

    rows, errors = read_rows("store", scratch_clone(origin_dir, git_env, "list"))

    assert [row.task.id for row in rows] == ["t1"]
    assert [error.split(":")[0] for error in errors] == [
        "store Old Notes",
        "store t0",
        "store t2",
        "store t3",
        "store t4",
    ]
    assert errors[2] == "store t2: .agent/t2/STATE.json is not UTF-8 text, on agent-notes. Fix it there."
    assert (
        errors[3]
        == errors[4].replace("t4", "t3")
        == ("store t3: .agent/t3/STATE.json is not a plain file, on agent-notes. Fix it there.")
    )


def test_a_project_without_a_notes_branch_has_no_rows(origin_dir, git_env) -> None:
    git(git_env, f"--git-dir={origin_dir}", "branch", "--quiet", "-D", task.NOTES_BRANCH)

    assert read_rows("store", scratch_clone(origin_dir, git_env, "list")) == ([], [])


def test_the_list_says_whose_turn_it_is_and_whether_its_sandbox_runs() -> None:
    def state(name: str, note: str = "") -> TaskState:
        return TaskState(lifecycle=FEATURE, state=name, note=note)

    rows = [
        Row("store", Task("t1"), state("implement", "R3 is open.\nSee REVIEW.md.")),
        Row("store", Task("t2"), state("review", "Ready.")),
        Row("store", Task("t3"), state("blocked", "Which base?")),
        Row("store", Task("t4"), state("done")),
    ]

    assert table(rows, live_sandboxes={"reviewer-store-t2"}) == [
        "PROJECT  TASK  LIFECYCLE  STATE      ROLE      SANDBOX  NOTE",
        "store    t1    feature    implement  dev       —        R3 is open.",
        "store    t2    feature    review     reviewer  running  Ready.",
        "store    t3    feature    blocked    —         —        Which base?",
        "store    t4    feature    done       —         —",
    ]
