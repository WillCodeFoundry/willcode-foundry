import os
import sys

import pytest

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import SystemHost


@pytest.fixture
def host() -> SystemHost:
    return SystemHost()


# --- run ------------------------------------------------------------------------


def test_run_executes_the_command_and_captures_output(host):
    result = host.run(["echo", "hi"])

    assert result.stdout == "hi\n"


def test_run_translates_a_missing_executable_into_sandboxerror(host):
    with pytest.raises(SandboxError, match="not-a-real-command not found in PATH"):
        host.run(["not-a-real-command"])


def test_run_passes_the_given_env_to_the_child_process(host):
    result = host.run(
        [sys.executable, "-c", "import os; print(os.environ.get('AGENT_SANDBOX_TEST_VALUE', ''), end='')"],
        env={"AGENT_SANDBOX_TEST_VALUE": "hello"},
    )

    assert result.stdout == "hello"


# --- environ ------------------------------------------------------------------


def test_environ_is_the_processs_own_environment(host):
    assert host.environ() is os.environ
