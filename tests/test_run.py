"""foundry run, up to the call into agent_sandbox: make_launch_request against a foundry under tmp_path, and which
task and role it launches."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent_runtime.agent_kit import AgentKit
from foundry import cli, config
from foundry.agent_sandbox import LaunchRequest, SandboxDefinition
from foundry.commands.run import choose_role, fetch_open_task, make_launch_request, role_for_turn
from foundry.config import Config
from foundry.errors import FoundryError
from foundry.project_tasks import MissingTurnError, ProjectTasks
from foundry.session import SessionVariables
from foundry.task import HUMAN, NOTES_BRANCH, Task
from tests.support import git

CONFIG = """\
name: test
projects:
  tkt-store: {url: "git@github.com:o/tkt-store.git"}
roles:
  dev: {}
  reviewer: {}
"""


@pytest.fixture
def foundry_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "foundry.yaml").write_text(CONFIG)
    for role_name in ("dev", "reviewer"):
        (tmp_path / "agent-kit" / "roles" / role_name).mkdir(parents=True)
        for name in ("ROLE.md", "gitconfig"):
            (tmp_path / "agent-kit" / "roles" / role_name / name).write_text("")
    return tmp_path


@pytest.fixture
def foundry_config(foundry_root: Path) -> Config:
    return config.load(foundry_root)


def request_for(foundry_root: Path, task_id: str = "wcf-0042") -> LaunchRequest:
    """make_launch_request for role dev on ``task_id`` in tkt-store, as this foundry's config has them."""
    foundry_config = config.load(foundry_root)
    return make_launch_request(
        foundry_root,
        project=foundry_config.project("tkt-store"),
        role=foundry_config.role("dev"),
        task=Task.as_open(task_id),
    )


def test_the_first_launch_asks_for_the_new_session_with_the_role_s_key(
    foundry_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    request = request_for(foundry_root)

    session_dir = foundry_root / "sessions" / "dev-tkt-store-wcf-0042"
    assert capsys.readouterr().err == f"==> session:   {session_dir} (new)\n"
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
    assert request.model is None


def test_the_role_s_model_is_passed_to_the_launch(foundry_root: Path) -> None:
    (foundry_root / "config" / "foundry.yaml").write_text(CONFIG.replace("dev: {}", "dev: {model: sonnet}"))

    assert request_for(foundry_root).model == "sonnet"


def test_a_failed_build_aborts_the_launch(foundry_root: Path) -> None:
    AgentKit(foundry_root / "agent-kit").runtime.parent.write_text("a file where the dir goes\n")

    with pytest.raises(FoundryError, match="can't build the agent runtime"):
        request_for(foundry_root)


def test_a_rerun_asks_for_the_same_launch_and_prints_no_new_session(
    foundry_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = request_for(foundry_root)
    capsys.readouterr()

    assert request_for(foundry_root) == first
    assert capsys.readouterr().err == ""


def test_a_token_file_is_passed_when_present(foundry_root: Path) -> None:
    token = foundry_root / "secrets" / "github" / "dev.token"
    token.parent.mkdir(parents=True)
    token.write_text("ghp_x")
    assert request_for(foundry_root).github_token_path == token


def test_run_prints_the_turn_and_the_new_session_then_calls_the_launcher(
    project_repository, git_env, foundry_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, up to the launcher's first check: the role has no SSH key, so the launch is refused there.

    sbx and ps are stand-ins that list no sandbox and no process, since the launcher prunes before that check. What
    comes after it needs a real sandbox: the sbx tier's."""
    project_repository.edit_notes(write={".agent/tasks/open/tst-0000/TURN": "dev\n"})
    (foundry_root / "config" / "foundry.yaml").write_text(
        CONFIG.replace('"git@github.com:o/tkt-store.git"', f"'{project_repository.path}'")
    )
    stand_ins = foundry_root / "stand-ins"
    stand_ins.mkdir()
    for name, script in {"sbx": "echo '{\"sandboxes\": []}'", "ps": "exit 0"}.items():
        (stand_ins / name).write_text(f"#!/bin/sh\n{script}\n")
        (stand_ins / name).chmod(0o755)
    monkeypatch.chdir(foundry_root)
    for name, value in git_env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("PATH", f"{stand_ins}:{git_env['PATH']}")

    assert cli.main(["run", "tkt-store", "tst-0000"]) == 1

    ssh_key_path = foundry_root / "secrets" / "ssh" / "dev"
    assert capsys.readouterr() == (
        "",
        "==> turn:      dev\n"
        f"==> session:   {foundry_root / 'sessions' / 'dev-tkt-store-tst-0000'} (new)\n"
        f"error: ssh key {str(ssh_key_path)!r} is not a file\n",
    )


# --- whose turn -----------------------------------------------------------------------


ROLES = ("dev", "reviewer")


def test_a_role_s_turn_launches_that_role() -> None:
    assert role_for_turn("reviewer", ROLES, project_name="tkt-store", task=Task.as_open("tst-0001")) == "reviewer"


def test_the_human_s_turn_is_refused_saying_how_to_start_a_role_anyway() -> None:
    with pytest.raises(FoundryError, match=r"tst-0001 is waiting for you.*foundry run tkt-store ROLE tst-0001"):
        role_for_turn(HUMAN, ROLES, project_name="tkt-store", task=Task.as_open("tst-0001"))


@pytest.mark.parametrize("turn", ["Human", "dev\nreviewer", "qa"])
def test_a_turn_that_names_no_role_is_refused_naming_the_turn_file(turn: str) -> None:
    with pytest.raises(
        FoundryError,
        match=(
            r"\.agent/tasks/open/tst-0001/TURN on agent-notes names .*, which is not a role; "
            rf"known: dev, reviewer, or {HUMAN}\. To start a role anyway: foundry run tkt-store ROLE tst-0001$"
        ),
    ):
        role_for_turn(turn, ROLES, project_name="tkt-store", task=Task.as_open("tst-0001"))


@pytest.mark.parametrize(
    ("argv", "role_name"),
    [(["run", "tkt-store", "tst-0001"], None), (["run", "tkt-store", "dev", "tst-0001"], "dev")],
    ids=["without ROLE", "with ROLE"],
)
def test_run_takes_an_optional_role_between_the_project_and_the_task(argv: list[str], role_name) -> None:
    args = cli.build_parser().parse_args(argv)
    assert (args.project_name, args.role_name, args.task_id) == ("tkt-store", role_name, "tst-0001")


@pytest.fixture
def project_tasks(tmp_path: Path, origin: Path) -> Iterator[ProjectTasks]:
    """The tasks of a repository whose agent-notes holds open tst-0001, whose turn is the reviewer's, closed
    tst-0002, and open tst-0003, which has no turn."""
    seed = tmp_path / "seed"
    git(seed, "switch", "-q", "--orphan", NOTES_BRANCH)
    for a_task in (Task.as_open("tst-0001"), Task.as_closed("tst-0002")):
        (seed / a_task.task_notes_dir).mkdir(parents=True)
        (seed / a_task.task_file).write_text("# Task\n")
        (seed / a_task.turn_file).write_text("reviewer\n")
    (seed / Task.as_open("tst-0003").task_notes_dir).mkdir(parents=True)
    (seed / Task.as_open("tst-0003").task_file).write_text("# Task\n")
    git(seed, "add", ".agent")
    git(seed, "commit", "-qm", "notes")
    git(seed, "push", "-q", "origin", NOTES_BRANCH)
    with ProjectTasks.in_scratch_clone(str(origin), os.environ) as project_tasks:
        yield project_tasks


@pytest.mark.parametrize("role_name, launched", [(None, "reviewer"), ("dev", "dev")], ids=["without ROLE", "with ROLE"])
def test_an_open_task_launches_the_role_named_or_else_the_turn_s(
    project_tasks: ProjectTasks, foundry_config: Config, role_name, launched
) -> None:
    task = fetch_open_task(project_tasks, project_name="tkt-store", task_id="tst-0001")
    role = choose_role(project_tasks, foundry_config, project_name="tkt-store", task=task, role_name=role_name)

    assert (task, role) == (Task.as_open("tst-0001"), foundry_config.role(launched))


def test_a_closed_task_is_refused_saying_how_to_reopen_it(project_tasks: ProjectTasks) -> None:
    with pytest.raises(
        FoundryError, match=r"^task tst-0002 is closed: reopen it with `foundry task reopen tkt-store tst-0002`$"
    ):
        fetch_open_task(project_tasks, project_name="tkt-store", task_id="tst-0002")


def test_a_task_without_a_turn_is_refused(project_tasks: ProjectTasks, foundry_config: Config) -> None:
    with pytest.raises(
        MissingTurnError,
        match=r"^task tst-0003 has no turn: agent-notes has no \.agent/tasks/open/tst-0003/TURN, or it is empty\.$",
    ):
        choose_role(
            project_tasks, foundry_config, project_name="tkt-store", task=Task.as_open("tst-0003"), role_name=None
        )


def test_a_role_not_in_the_config_is_refused(project_tasks: ProjectTasks, foundry_config: Config) -> None:
    with pytest.raises(FoundryError, match=r"unknown role 'qa'; known: dev, reviewer"):
        choose_role(
            project_tasks, foundry_config, project_name="tkt-store", task=Task.as_open("tst-0001"), role_name="qa"
        )
