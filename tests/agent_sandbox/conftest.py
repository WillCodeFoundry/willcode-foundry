"""agent_sandbox's fakes, handed to tests as fixtures, so no test imports from tests/."""

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from foundry.agent_sandbox.host import Host
from foundry.agent_sandbox.sandbox import Sandbox

Response = str | int | tuple[int, str]


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
        self.terminal_runs: list[tuple[tuple[str, ...], Mapping[str, str]]] = []
        """What run_in_terminal was given, in order; it returns 0 for each."""

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

    def run_in_terminal(self, command: Sequence[str], env: Mapping[str, str]) -> int:
        self.terminal_runs.append((tuple(command), env))
        return 0

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


class FakeSandbox:
    """A sandbox in memory, as agent_sandbox.sandbox.Sandbox describes it.

    A test sets up what the sandbox is like (whether it exists and runs, what keys reach it, which commands
    fail inside, whether an agent runs in it), then checks where it ended up. A command run inside prints
    "ran <command>".
    """

    def __init__(
        self,
        *,
        exists: bool = False,
        forwarded_key_fingerprints: set[str] | None = None,
        exit_codes_by_command: Mapping[tuple[str, ...], int] | None = None,
        stderr_by_command: Mapping[tuple[str, ...], str] | None = None,
        running: bool = True,
        agent_running: bool = False,
    ) -> None:
        self.exists = exists
        self.running = running
        """What is_running says; ensure_running sets it."""
        self.agent_running = agent_running
        self.attached_models: list[str | None] = []
        """The model each attach was given, in order."""
        self.created = False
        self.has_github_ssh_access = False
        self.github_token_file: Path | None = None
        self.commands_run: list[tuple[str, ...]] = []
        self._forwarded_key_fingerprints = forwarded_key_fingerprints
        self._exit_codes_by_command = dict(exit_codes_by_command or {})
        self._stderr_by_command = dict(stderr_by_command or {})

    def ensure_running(self) -> None:
        self.created = not self.exists
        self.exists = True
        self.running = True

    def is_running(self) -> bool:
        return self.running

    def is_agent_running(self) -> bool:
        return self.agent_running

    def stop_hint(self) -> str:
        return "stop it with `sbx stop fake`"

    def give_github_ssh_access(self) -> None:
        self.has_github_ssh_access = True

    def set_github_token_file(self, github_token_path: Path | None) -> None:
        self.github_token_file = github_token_path

    def forwarded_key_fingerprints(self) -> set[str] | None:
        return None if self._forwarded_key_fingerprints is None else set(self._forwarded_key_fingerprints)

    def run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        self.commands_run.append(command)
        code = self._exit_codes_by_command.get(command, 0)
        stderr = self._stderr_by_command.get(command, "")
        return subprocess.CompletedProcess(command, code, stdout=f"ran {' '.join(command)}\n", stderr=stderr)

    def attach(self, model: str | None) -> None:
        self.attached_models.append(model)


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
