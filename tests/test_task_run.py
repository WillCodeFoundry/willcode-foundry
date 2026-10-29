"""foundry task run, up to the hand-over to agent_sandbox: prepare_launch against a foundry under tmp_path, and
whose_turn, which picks the role it launches."""

from pathlib import Path

import pytest

from agent_runtime.agent_kit import AgentKit
from agent_runtime.task.lifecycles import FEATURE
from agent_runtime.task.state import TaskState
from foundry import config
from foundry.agent_sandbox import SandboxDefinition
from foundry.commands.task import Launch, prepare_launch, whose_turn
from foundry.errors import FoundryError
from foundry.session import SessionVariables
from foundry.task import Task

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


def launch_dev(foundry_root: Path, project_name: str = "tkt-store", role_name: str = "dev") -> Launch:
    """prepare_launch for the dev on tkt-store's WCF-0042, with the foundry's config as run_main loads it."""
    foundry_config = config.load(foundry_root)
    project = foundry_config.project(project_name)
    return prepare_launch(foundry_root, foundry_config, project=project, role_name=role_name, task=Task("WCF-0042"))


def test_the_first_launch_asks_for_the_new_session_with_the_role_s_key(foundry_root: Path) -> None:
    launch = launch_dev(foundry_root)
    request = launch.request

    assert launch.created

    session_dir = foundry_root / "sessions" / "dev-tkt-store-wcf-0042"
    assert request.definition_dir == session_dir
    assert SessionVariables.from_env(SandboxDefinition.read(session_dir).variables).task == Task("wcf-0042")
    assert request.init_command == (
        "/usr/bin/python3",
        "-IS",
        str(AgentKit(foundry_root / "agent-kit").runtime),
        "session-init",
    )
    assert request.ssh_key_path == foundry_root / "secrets" / "ssh" / "dev"
    assert request.github_token_path is None


def test_the_runtime_is_built_into_the_kit(foundry_root: Path) -> None:
    launch_dev(foundry_root)

    assert AgentKit(foundry_root / "agent-kit").runtime.is_file()


def test_a_failed_build_aborts_the_launch(foundry_root: Path) -> None:
    AgentKit(foundry_root / "agent-kit").runtime.parent.write_text("a file where the folder goes\n")

    with pytest.raises(FoundryError, match="can't build the agent runtime"):
        launch_dev(foundry_root)


def test_a_rerun_asks_for_the_same_launch(foundry_root: Path) -> None:
    first = launch_dev(foundry_root)
    again = launch_dev(foundry_root)
    assert (again.request, again.created) == (first.request, False)


def test_a_token_file_is_passed_when_present(foundry_root: Path) -> None:
    token = foundry_root / "secrets" / "github" / "dev.token"
    token.parent.mkdir(parents=True)
    token.write_text("ghp_x")
    assert launch_dev(foundry_root).request.github_token_path == token


@pytest.mark.parametrize(
    ("project_name", "role_name", "message"),
    [("nope", "dev", "unknown project 'nope'"), ("tkt-store", "qa", "unknown role 'qa'; known: dev")],
)
def test_unknown_names_are_reported(foundry_root: Path, project_name: str, role_name: str, message: str) -> None:
    with pytest.raises(FoundryError, match=message):
        launch_dev(foundry_root, project_name, role_name)


# --- whose turn ----------------------------------------------------------------


def in_state(state: str, note: str = "") -> TaskState:
    return TaskState(lifecycle=FEATURE, state=state, note=note)


@pytest.mark.parametrize(
    ("state", "role"), [("plan", "planner"), ("implement", "dev"), ("review", "reviewer"), ("deliver", "dev")]
)
def test_the_role_launched_is_the_one_whose_turn_it_is(state: str, role: str) -> None:
    assert whose_turn(in_state(state), project_name="store", task=Task("t1")) == role


@pytest.mark.parametrize(("state", "note"), [("blocked", "Is R4 in scope?"), ("done", "PR: https://example.com/pr/1")])
def test_a_terminal_task_is_refused_with_its_note_where_it_came_from_and_how_to_move_it_on(
    state: str, note: str
) -> None:
    with pytest.raises(FoundryError) as refused:
        whose_turn(in_state(state, note), project_name="store", task=Task("t1"))

    assert str(refused.value) == (
        f"task t1 is {state}, where no role works: {note}\n"
        "  where it came from: git log origin/agent-notes -- .agent/t1/STATE.json\n"
        "  to move it on: foundry task move store t1 STATE --note …"
    )
