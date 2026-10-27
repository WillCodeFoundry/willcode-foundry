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

    assert environ.agent_task == "t1"
    assert environ.agent_task_branch == variables.task.branch
    assert environ.agent_kit_dir == variables.agent_kit_dir
    assert environ.agent_notes_dir == Path(variables.notes_dir)


def test_every_missing_variable_is_named_at_once() -> None:
    with pytest.raises(contract.MissingVariables) as raised:
        contract.read_environ({contract.TASK: "t1", contract.ROLE: ""})

    missing = ", ".join(name for name in contract.NAMES if name != contract.TASK)
    assert str(raised.value) == f"{missing} not set; this runs inside a foundry sandbox, which sets them"
