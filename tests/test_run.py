"""foundry run, up to the hand-over to agent_sandbox: prepare_launch against a foundry under tmp_path, and whose
turn it launches."""

import os
from pathlib import Path

import pytest

from agent_runtime.agent_kit import AgentKit
from foundry import cli
from foundry.agent_sandbox import SandboxDefinition
from foundry.commands.run import prepare_launch, require_open, role_for_turn
from foundry.errors import FoundryError
from foundry.project_clone import ProjectClone
from foundry.project_tasks import ProjectTasks
from foundry.session import SessionVariables
from foundry.task import HUMAN, NOTES_BRANCH, Task
from tests.support import git

CONFIG = """\
name: test
projects:
  tkt-store: {url: "git@github.com:o/tkt-store.git"}
roles:
  dev: {}
"""


@pytest.fixture
def foundry_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    (tmp_path / "agent-kit" / "roles" / "dev").mkdir(parents=True)
    for name in ("ROLE.md", "gitconfig"):
        (tmp_path / "agent-kit" / "roles" / "dev" / name).write_text("")
    return tmp_path


def test_the_first_launch_asks_for_the_new_session_with_the_role_s_key(foundry_root: Path) -> None:
    launch = prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task.as_open("WCF-0042"))
    request = launch.request

    assert launch.created

    session_dir = foundry_root / "sessions" / "dev-tkt-store-wcf-0042"
    assert request.definition_dir == session_dir
    assert SessionVariables.from_env(SandboxDefinition.read(session_dir).variables).task == Task.as_open("wcf-0042")
    assert request.init_command == (
        "/usr/bin/python3",
        "-IS",
        str(AgentKit(foundry_root / "agent-kit").runtime),
        "session-init",
    )
    assert request.ssh_key_path == foundry_root / "secrets" / "ssh" / "dev"
    assert request.github_token_path is None


def test_the_runtime_is_built_into_the_kit(foundry_root: Path) -> None:
    prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task.as_open("WCF-0042"))

    assert AgentKit(foundry_root / "agent-kit").runtime.is_file()


def test_a_failed_build_aborts_the_launch(foundry_root: Path) -> None:
    AgentKit(foundry_root / "agent-kit").runtime.parent.write_text("a file where the folder goes\n")

    with pytest.raises(FoundryError, match="can't build the agent runtime"):
        prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task.as_open("WCF-0042"))


def test_a_rerun_asks_for_the_same_launch(foundry_root: Path) -> None:
    first = prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task.as_open("WCF-0042"))
    again = prepare_launch(foundry_root, project_name="tkt-store", role_name="dev", task=Task.as_open("WCF-0042"))
    assert (again.request, again.created) == (first.request, False)


def test_a_token_file_is_passed_when_present(foundry_root: Path) -> None:
    token = foundry_root / "secrets" / "github" / "dev.token"
    token.parent.mkdir(parents=True)
    token.write_text("ghp_x")
    assert (
        prepare_launch(
            foundry_root, project_name="tkt-store", role_name="dev", task=Task.as_open("WCF-0042")
        ).request.github_token_path
        == token
    )


@pytest.mark.parametrize(
    ("project_name", "role_name", "message"),
    [("nope", "dev", "unknown project 'nope'"), ("tkt-store", "qa", "unknown role 'qa'; known: dev")],
)
def test_unknown_names_are_reported(foundry_root: Path, project_name: str, role_name: str, message: str) -> None:
    with pytest.raises(FoundryError, match=message):
        prepare_launch(foundry_root, project_name=project_name, role_name=role_name, task=Task.as_open("t1"))


# --- whose turn -----------------------------------------------------------------------


ROLES = ("dev", "reviewer")


def test_a_role_s_turn_launches_that_role() -> None:
    assert role_for_turn("reviewer", ROLES, project_name="tkt-store", task=Task.as_open("t1")) == "reviewer"


def test_the_human_s_turn_is_refused_saying_how_to_start_a_role_anyway() -> None:
    with pytest.raises(FoundryError, match=r"t1 is waiting for you.*foundry run tkt-store ROLE t1"):
        role_for_turn(HUMAN, ROLES, project_name="tkt-store", task=Task.as_open("t1"))


@pytest.mark.parametrize("turn", ["Human", "dev\nreviewer", "qa"])
def test_a_turn_that_names_no_role_is_refused_naming_the_turn_file(turn: str) -> None:
    with pytest.raises(FoundryError, match=r"\.agent/tasks/open/t1/TURN on agent-notes names .*not a role.*ROLE t1"):
        role_for_turn(turn, ROLES, project_name="tkt-store", task=Task.as_open("t1"))


@pytest.mark.parametrize(
    ("argv", "role_name"),
    [(["run", "tkt-store", "t1"], None), (["run", "tkt-store", "dev", "t1"], "dev")],
    ids=["without ROLE", "with ROLE"],
)
def test_run_takes_an_optional_role_between_the_project_and_the_task(argv: list[str], role_name) -> None:
    args = cli.build_parser().parse_args(argv)
    assert (args.project_name, args.role_name, args.task_id) == ("tkt-store", role_name, "t1")


def test_a_closed_task_is_refused_saying_how_to_reopen_it(tmp_path: Path, origin: Path) -> None:
    seed = tmp_path / "seed"
    git(seed, "switch", "-q", "--orphan", NOTES_BRANCH)
    closed = Task.as_closed("t1")
    (seed / closed.task_notes_dir).mkdir(parents=True)
    (seed / closed.task_file).write_text("# Task\n")
    git(seed, "add", closed.task_notes_dir)
    git(seed, "commit", "-qm", "closed")
    git(seed, "push", "-q", "origin", NOTES_BRANCH)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    tasks = ProjectTasks(ProjectClone.init(str(origin), scratch, os.environ))

    with pytest.raises(FoundryError, match=r"task t1 is closed.*foundry task reopen tkt-store t1"):
        require_open(tasks, project_name="tkt-store", task=Task.as_open("t1"))
    require_open(tasks, project_name="tkt-store", task=Task.as_open("t2"))  # not closed: no refusal
