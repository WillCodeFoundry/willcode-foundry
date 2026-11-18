"""The boundary to the host machine's processes: every external command goes through here."""

import os
import signal
import subprocess
from collections.abc import Mapping, Sequence
from types import FrameType
from typing import Protocol

from foundry.agent_sandbox.errors import SandboxError


class Host(Protocol):
    def run(self, command: Sequence[str], *, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run a command to completion, capturing its output (like subprocess.run)."""
        ...

    def run_in_terminal(self, command: Sequence[str], env: Mapping[str, str]) -> int:
        """Run a command on this process's terminal, and wait for it: its exit code, or minus the signal that killed
        it. An interrupt meanwhile does nothing to this process; the command gets it as it would without us."""
        ...

    def environ(self) -> Mapping[str, str]:
        """This process's own environment."""
        ...

    def list_processes(self, uid: int) -> list[tuple[int, str]]:
        """Every process of ``uid``, as (process id, command line)."""
        ...

    def kill_process(self, pid: int) -> None:
        """Send SIGTERM; raises ProcessLookupError if there's no such process."""
        ...


class SystemHost:
    def run(self, command: Sequence[str], *, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                list(command),
                check=False,  # callers inspect returncode; a non-zero exit is not an exception here
                env=None if env is None else dict(env),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise SandboxError(f"{command[0]} not found in PATH") from None

    def run_in_terminal(self, command: Sequence[str], env: Mapping[str, str]) -> int:
        """SIGINT gets a handler that does nothing, not SIG_IGN: exec resets a caught signal to its default in the
        child, but keeps an ignored one ignored."""
        previous_handler = signal.signal(signal.SIGINT, _outlive_interrupt_handler)
        try:
            return subprocess.run(list(command), env=dict(env), check=False).returncode
        except FileNotFoundError:
            raise SandboxError(f"{command[0]} not found in PATH") from None
        finally:
            signal.signal(signal.SIGINT, previous_handler)

    def environ(self) -> Mapping[str, str]:
        return os.environ

    def list_processes(self, uid: int) -> list[tuple[int, str]]:
        result = self.run(("ps", "-u", str(uid), "-o", "pid=,command="))
        if result.returncode != 0:
            raise SandboxError(f"could not list running processes: {result.stderr.strip()}")
        processes = []
        for line in result.stdout.splitlines():
            pid, _, command = line.strip().partition(" ")
            processes.append((int(pid), command.strip()))
        return processes

    def kill_process(self, pid: int) -> None:
        os.kill(pid, signal.SIGTERM)


def _outlive_interrupt_handler(_signal_number: int, _frame: FrameType | None) -> None:
    """A signal handler for a signal this process outlives."""
