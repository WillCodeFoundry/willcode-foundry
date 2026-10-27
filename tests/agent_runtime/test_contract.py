"""agent_runtime.contract: the session variables, read back as the sandbox definition set them."""

import subprocess
import sys
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


def test_a_command_runs_the_kits_runtime_isolated() -> None:
    assert contract.command(Path("/kit"), "hook", "guard-bash") == (
        "/usr/bin/python3",
        "-IS",
        "/kit/.build/agent_runtime.pyz",
        "hook",
        "guard-bash",
    )


def test_the_flags_isolate_the_runtime_and_skip_site() -> None:
    """-I ignores PYTHON* variables and user site-packages, and -S skips site, so no .pth file in any
    site-packages runs. One argument, as a shebang line passes."""
    flags = subprocess.run(
        [sys.executable, contract.PYTHON_FLAGS, "-c", "import sys; print(sys.flags.isolated, sys.flags.no_site)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert flags.stdout == "1 1\n"
