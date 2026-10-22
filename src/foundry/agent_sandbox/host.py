"""The boundary to the host machine: every external command and filesystem privilege check goes through here."""

import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn, Protocol

from foundry.agent_sandbox.errors import SandboxError


class HostPort(Protocol):
    def run(self, command: Sequence[str], *, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run a command to completion, capturing its output (like subprocess.run)."""
        ...

    def exec(self, command: Sequence[str], env: Mapping[str, str]) -> NoReturn:
        """Replace the current process with command (like os.execvpe)."""
        ...

    def environ(self) -> Mapping[str, str]:
        """This process's own environment."""
        ...

    def ensure_private_dir(self, dir_path: Path) -> None:
        """Create dir_path as a directory only this user can use; raise if it isn't one."""
        ...

    def reset_socket(self, socket_path: Path) -> None:
        """Make socket_path ready for a fresh ssh-agent: private parent dir, no leftover socket file."""
        ...

    def ssh_agent_socket_path(self, sockets_dir_path: Path, sandbox_name: str) -> Path:
        """The ssh-agent socket for the sandbox, under a directory private to this user."""
        ...

    def ensure_dir_exists(self, dir_path: Path, what: str) -> None:
        """Raise if dir_path is not a directory."""
        ...

    def ensure_file_exists(self, file_path: Path, what: str) -> None:
        """Raise if file_path is not a file."""
        ...


class Host:
    def __init__(self, uid: int) -> None:
        self._uid = uid

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

    def ensure_private_dir(self, dir_path: Path) -> None:
        """Create dir_path as a directory only this user can use, refusing one we don't own.

        The sockets directory lives in /tmp, which is shared: another user could
        create it first, or put a symlink there pointing somewhere they control.
        """
        try:
            dir_path.mkdir(mode=0o700, exist_ok=True)
            info = os.lstat(dir_path)
            ours = stat.S_ISDIR(info.st_mode) and info.st_uid == self._uid
        except FileExistsError:  # a file, or a dangling symlink
            ours = False
        if not ours:
            raise SandboxError(f"{dir_path} is not a directory owned by you")
        dir_path.chmod(0o700)

    def reset_socket(self, socket_path: Path) -> None:
        self.ensure_private_dir(socket_path.parent)
        socket_path.unlink(missing_ok=True)

    def ssh_agent_socket_path(self, sockets_dir_path: Path, sandbox_name: str) -> Path:
        return sockets_dir_path.with_name(f"{sockets_dir_path.name}-{self._uid}") / f"{sandbox_name}.sock"

    def ensure_dir_exists(self, dir_path: Path, what: str) -> None:
        if not dir_path.is_dir():
            raise SandboxError(f"{what} {str(dir_path)!r} is not a directory")

    def ensure_file_exists(self, file_path: Path, what: str) -> None:
        if not file_path.is_file():
            raise SandboxError(f"{what} {str(file_path)!r} is not a file")
