"""agent_runtime.contract: the session variables, read back as the sandbox definition set them."""

from collections.abc import Callable
from pathlib import Path

import pytest

from agent_runtime import contract
from foundry import session
from foundry.task import Task


def test_the_variables_a_session_sets_are_read_back(
    session_variables: Callable[[Task], contract.SessionVariables],
) -> None:
    variables = session_variables(Task.as_open("tst-0001"))

    assert variables.agent_task_id == "tst-0001"
    assert variables.agent_task_branch == Task.as_open("tst-0001").branch
    assert variables.agent_notes_checkout_dir == Path(f"{variables.agent_code_checkout_dir}-notes")


def test_variables_read_back_are_the_variables_written() -> None:
    variables = session.session_variables(
        role_name="dev",
        task=Task.as_open("tst-0001"),
        repo_url="u",
        agent_kit_dir=Path("/kit"),
        code_checkout_dir=Path("/w/p"),
    )

    assert contract.read_session_variables(variables.to_env()) == variables
    assert list(variables.to_env()) == list(contract.NAMES)


def test_every_missing_variable_is_named_at_once() -> None:
    with pytest.raises(contract.MissingVariables) as raised:
        contract.read_session_variables({contract.TASK_ID: "tst-0001", contract.ROLE: ""})

    missing = ", ".join(name for name in contract.NAMES if name != contract.TASK_ID)
    assert str(raised.value) == f"{missing} not set; this runs inside a foundry sandbox, which sets them"
