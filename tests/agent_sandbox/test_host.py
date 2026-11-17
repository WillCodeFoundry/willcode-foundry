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


def test_environ_is_this_process_environment(host):
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


def test_kill_process_raises_for_a_process_that_has_gone(host):
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()

    with pytest.raises(ProcessLookupError):
        host.kill_process(child.pid)


# --- run_in_terminal ------------------------------------------------------------

_SIGINT_BIT = 1 << (signal.SIGINT - 1)


def test_run_in_terminal_returns_the_exit_code_and_an_interrupt_meanwhile_leaves_this_process_alive(host):
    """A Ctrl-C that reaches foundry while it waits can't kill it before the checkout status (AC4)."""
    interrupt_parent = "import os, signal, sys; os.kill(os.getppid(), signal.SIGINT); sys.exit(3)"

    assert host.run_in_terminal([sys.executable, "-c", interrupt_parent], os.environ) == 3


def test_run_in_terminal_returns_a_killed_child_s_signal_without_raising(host):
    """sbx run killed from elsewhere still ends in a report (AC4)."""
    kill_itself = "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"

    assert host.run_in_terminal([sys.executable, "-c", kill_itself], os.environ) == -signal.SIGKILL


def test_run_in_terminal_puts_the_interrupt_handler_back(host):
    before = signal.getsignal(signal.SIGINT)

    host.run_in_terminal(["true"], os.environ)

    assert signal.getsignal(signal.SIGINT) is before


def test_run_in_terminal_starts_the_child_with_the_default_interrupt_handler(host, tmp_path):
    """Neither ignored nor caught, so sbx and Claude Code get Ctrl-C as before (AC6). grep reads its own status."""
    status = tmp_path / "status"
    read_own_status = f"exec grep -E '^Sig(Ign|Cgt):' /proc/self/status > {status}"

    assert host.run_in_terminal(["sh", "-c", read_own_status], os.environ) == 0

    masks = dict(line.split(":") for line in status.read_text().splitlines())
    assert int(masks["SigIgn"], 16) & _SIGINT_BIT == 0
    assert int(masks["SigCgt"], 16) & _SIGINT_BIT == 0


def test_run_in_terminal_translates_a_missing_executable_into_sandboxerror(host):
    with pytest.raises(SandboxError, match="not-a-real-command not found in PATH"):
        host.run_in_terminal(["not-a-real-command"], os.environ)
