"""A temporary machine: the second adapter behind harden.Machine, for running hardening without root.

The agent is modelled as a user who is neither the owner nor in the group of what it touches: it can write a
path when the path's "other" bits say so (for a link, its target's). In a test the root owner and the agent are
the same user, so os.access would report every file root mode installs as writable. Ownership is modelled too:
every path is root's, the test user's here, unless a test puts another owner in the table.
"""

import contextlib
import dataclasses
import os
import socket
import stat
from collections.abc import Iterator
from pathlib import Path

from agent_runtime import harden

ME = harden.Owner(os.getuid(), os.getgid())
SOMEONE_ELSE = harden.Owner(os.getuid() + 1, os.getgid())
SUDO_USER = harden.SANDBOX_USER


# --- helpers -------------------------------------------------------------------------


def make_socket(socket_path: Path, mode: int) -> Path:
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(socket_path))
    socket_path.chmod(mode)
    return socket_path


def stand_in(tmp_path: Path, name: str, exit_code: int) -> str:
    """A command that only exits with the code given, replacing any file of that name, as a new one."""
    command = tmp_path / name
    command.unlink(missing_ok=True)  # it may be the stand-in root mode left mode 0
    command.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    command.chmod(0o755)
    return str(command)


@contextlib.contextmanager
def read_only(kit: Path) -> Iterator[None]:
    """The kit as its mount makes it, as far as file modes can: nothing in it writable by its owner."""
    paths = [kit, *kit.rglob("*")]
    for path in paths:
        if not path.is_symlink():
            path.chmod(0o555 if path.is_dir() else 0o444)
    try:
        yield
    finally:
        for path in paths:
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)


AGENT_UID = 4242
"""The agent's uid in agent mode; root mode runs as 0. Only what harden reads through the machine sees them."""


def other_can_write(path: Path) -> bool:
    try:
        return bool(path.stat().st_mode & stat.S_IWOTH)
    except OSError:
        return False


def recording_stand_in(directory: Path, name: str) -> tuple[str, Path]:
    """A command that records the arguments of each run, one line each, and exits 0."""
    log = directory / f"{name}.log"
    command = directory / name
    command.write_text(f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{log}"\n')
    command.chmod(0o755)
    return str(command), log


@dataclasses.dataclass(frozen=True)
class TemporaryMachine:
    """What a test needs to hand harden a machine, and to look at it afterwards."""

    root_mode: harden.Machine
    """The machine as root mode sees it: effective uid 0."""
    dir: Path
    """Every file the machine holds, except its sockets."""
    passwd_log: Path
    owners: dict[Path, int]
    """Who owns a path, where a test says someone else does; any other path is the test user's, root's here."""

    @property
    def agent_mode(self) -> harden.Machine:
        """The same machine as the agent sees it."""
        return dataclasses.replace(self.root_mode, euid=lambda: AGENT_UID)


@contextlib.contextmanager
def writable(directory: Path) -> Iterator[None]:
    """Let the test, as the kit's owner, add something to a read-only folder of it."""
    directory.chmod(0o755)
    try:
        yield
    finally:
        directory.chmod(0o555)


def assert_refused(kit: Path, machine: harden.Machine, *lines: str, startswith: str = "") -> None:
    """the check finds something the agent can still do, and says each of ``lines``."""
    failures = harden.check(kit, machine)
    assert failures
    for line in lines:
        assert line in failures, failures
    if startswith:
        assert any(failure.startswith(startswith) for failure in failures), failures
