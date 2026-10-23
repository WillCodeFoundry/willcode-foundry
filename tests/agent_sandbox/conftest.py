import subprocess
from collections.abc import Mapping, Sequence
from typing import NoReturn

import pytest

from foundry.agent_sandbox.host import Host

Response = str | int | tuple[int, str]


class ExecCalled(Exception):
    """Raised by FakeHost.exec instead of replacing the process, carrying what would have run."""

    def __init__(self, command: tuple[str, ...], env: Mapping[str, str]) -> None:
        self.command = command
        self.env = env


class FakeHost:
    """Answers commands from ``responses`` and records them in ``calls``.

    A response is stdout (str, exit 0), an exit code (int), an (exit code,
    stdout) pair, or a list of those, used in turn. An unexpected command
    raises KeyError.
    """

    def __init__(self) -> None:
        self.responses: dict[tuple[str, ...], Response | list[Response]] = {}
        self.calls: list[tuple[tuple[str, ...], Mapping[str, str] | None]] = []
        self.environ_value: Mapping[str, str] = {}
        self.processes: list[tuple[int, str]] = []
        """What list_processes returns, for any uid."""
        self.killed: list[int] = []
        """The process ids kill_process was given, in order."""
        self.gone: set[int] = set()
        """Process ids kill_process raises ProcessLookupError for."""

    def run(self, command: Sequence[str], *, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        self.calls.append((command, env))
        response = self.responses[command]
        if isinstance(response, list):
            response = response.pop(0)
        if isinstance(response, tuple):
            returncode, stdout = response
            return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="")
        if isinstance(response, int):
            return subprocess.CompletedProcess(command, response, stdout="", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=response, stderr="")

    def exec(self, command: Sequence[str], env: Mapping[str, str]) -> NoReturn:
        raise ExecCalled(tuple(command), env)

    def environ(self) -> Mapping[str, str]:
        return self.environ_value

    def list_processes(self, uid: int) -> list[tuple[int, str]]:
        return list(self.processes)

    def kill_process(self, pid: int) -> None:
        if pid in self.gone:
            raise ProcessLookupError(pid)
        self.killed.append(pid)

    @property
    def commands(self) -> list[tuple[str, ...]]:
        return [command for command, _ in self.calls]


@pytest.fixture
def host() -> FakeHost:
    host = FakeHost()
    _: Host = host
    return host
