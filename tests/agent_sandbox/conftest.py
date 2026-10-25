"""agent_sandbox's fakes, handed to tests as fixtures, so no test imports from tests/.

The foundry package's fakes are in tests/fakes.py.
"""

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn

import pytest

from foundry.agent_sandbox.host import Host
from foundry.agent_sandbox.sandbox import Sandbox

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

    ExecCalled = ExecCalled
    """What exec raises, so a test can catch it as host.ExecCalled without importing it."""

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


class Attached(Exception):
    """Raised by FakeSandbox.attach instead of handing this process over."""


class FakeSandbox:
    """A sandbox in memory, as agent_sandbox.sandbox.Sandbox describes it.

    A test sets up what the sandbox is like (whether it exists, what keys reach it, which commands
    fail inside), then checks where it ended up.
    """

    def __init__(
        self,
        *,
        exists: bool = False,
        forwarded_key_fingerprints: set[str] | None = None,
        exit_codes_by_command: Mapping[tuple[str, ...], int] | None = None,
    ) -> None:
        self.exists = exists
        self.created = False
        self.github_ssh_allowed = False
        self.github_host_keys_trusted = False
        self.github_token_file: Path | None = None
        self.commands_run: list[tuple[str, ...]] = []
        self._forwarded_key_fingerprints = forwarded_key_fingerprints
        self._exit_codes_by_command = dict(exit_codes_by_command or {})

    def start_if_exists(self) -> bool:
        return self.exists

    def create(self) -> None:
        self.exists = self.created = True

    def allow_github_ssh(self) -> None:
        self.github_ssh_allowed = True

    def trust_github_host_keys(self) -> None:
        self.github_host_keys_trusted = True

    def set_github_token_file(self, github_token_path: Path | None) -> None:
        self.github_token_file = github_token_path

    def forwarded_key_fingerprints(self) -> set[str] | None:
        return None if self._forwarded_key_fingerprints is None else set(self._forwarded_key_fingerprints)

    def run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        self.commands_run.append(command)
        return subprocess.CompletedProcess(command, self._exit_codes_by_command.get(command, 0), stdout="", stderr="")

    def attach(self) -> NoReturn:
        raise Attached()


_: type[Sandbox] = FakeSandbox  # FakeSandbox implements the port


@pytest.fixture
def host() -> FakeHost:
    host = FakeHost()
    _: Host = host
    return host


@pytest.fixture
def make_sandbox() -> type[FakeSandbox]:
    """FakeSandbox, to call with what the sandbox is like: make_sandbox(exists=True)."""
    return FakeSandbox
