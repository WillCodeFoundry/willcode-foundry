import os
import signal
import subprocess
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


# --- list_processes / kill_process ----------------------------------------------


def test_list_processes_includes_this_test_process(host):
    processes = dict(host.list_processes(os.getuid()))

    assert os.getpid() in processes
    assert processes[os.getpid()]  # its command line


def test_kill_process_stops_a_running_process(host):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])

    host.kill_process(child.pid)

    assert child.wait(timeout=10) == -signal.SIGTERM


def test_kill_process_counts_an_exited_process_as_stopped(host):
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()

    host.kill_process(child.pid)  # no error
