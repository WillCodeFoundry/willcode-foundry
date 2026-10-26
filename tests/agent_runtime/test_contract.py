"""agent_runtime.contract: the session variables, read back as the sandbox definition set them."""

from collections.abc import Callable
from pathlib import Path

import pytest

from agent_runtime import contract
from foundry.session import SessionVariables
from foundry.task import Task


def test_the_variables_a_session_sets_are_read_back(session_variables: Callable[[Task], SessionVariables]) -> None:
    variables = session_variables(Task("t1"))

    environ = contract.read_environ(variables.to_env())

    assert environ.task == "t1"
    assert environ.task_branch == variables.task.branch
    assert environ.kit_dir == variables.agent_kit_dir
    assert environ.notes_dir == Path(variables.notes_dir)


def test_every_missing_variable_is_named_at_once() -> None:
    with pytest.raises(contract.MissingVariables) as raised:
        contract.read_environ({contract.TASK: "t1", contract.ROLE: ""})

    assert raised.value.names == [name for name in contract.NAMES if name != contract.TASK]
    assert "AGENT_ROLE, AGENT_KIT_DIR" in str(raised.value)


def test_hardening_needs_only_the_kit() -> None:
    assert contract.read_kit_dir({contract.KIT_DIR: "/kit"}) == Path("/kit")
    with pytest.raises(contract.MissingVariables, match="AGENT_KIT_DIR not set"):
        contract.read_kit_dir({})


def test_a_command_runs_the_kits_runtime_isolated() -> None:
    assert contract.command(Path("/kit"), "hook", "guard-bash") == (
        "/usr/bin/python3",
        "-I",
        "/kit/.build/agent_runtime.pyz",
        "hook",
        "guard-bash",
    )
