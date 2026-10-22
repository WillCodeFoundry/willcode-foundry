"""The boundary to the host machine's processes: every external command goes through here."""

import os
import subprocess
from collections.abc import Mapping, Sequence
from typing import NoReturn, Protocol

from foundry.agent_sandbox.errors import SandboxError


class Host(Protocol):
    def run(self, command: Sequence[str], *, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run a command to completion, capturing its output (like subprocess.run)."""
        ...

    def exec(self, command: Sequence[str], env: Mapping[str, str]) -> NoReturn:
        """Replace the current process with command (like os.execvpe)."""
        ...

    def environ(self) -> Mapping[str, str]:
        """This process's own environment."""
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

    def exec(self, command: Sequence[str], env: Mapping[str, str]) -> NoReturn:
        os.execvpe(command[0], list(command), dict(env))

    def environ(self) -> Mapping[str, str]:
        return os.environ
