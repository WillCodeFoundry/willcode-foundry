"""agent-kit/bin/task, the stub the agent runs: it execs the runtime's task command through the link root mode
makes. The command itself is tested in-process in tests/agent_runtime/test_task_command.py."""

import os

from agent_runtime import hardening
from agent_runtime.agent_kit import PYTHON, PYTHON_FLAGS, AgentKit
from tests.support import AGENT_KIT_SOURCE


def test_the_task_stub_execs_the_hardened_runtimes_task_command() -> None:
    stub = AgentKit(AGENT_KIT_SOURCE).task_command
    lines = stub.read_text().splitlines()

    assert lines[0] == "#!/bin/sh"
    assert lines[-1] == f'exec {PYTHON} {PYTHON_FLAGS} {hardening.SANDBOX.hooks_runtime_link} task "$@"'
    assert os.access(stub, os.X_OK)
