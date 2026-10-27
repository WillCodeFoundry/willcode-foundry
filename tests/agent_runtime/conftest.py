"""Fixtures for the runtime's in-process tests: a temporary machine to harden, and a kit to harden it with."""

import functools
import shutil
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from agent_runtime import harden
from agent_runtime.agent_kit import AgentKit
from tests.support import AGENT_KIT_SOURCE
from tests.support.machine import (
    ME,
    SUDO_USER,
    TemporaryMachine,
    assert_refused,
    make_socket,
    other_can_write,
    read_only,
    recording_stand_in,
    stand_in,
)


@pytest.fixture
def socket_dir() -> Iterator[Path]:
    """A short directory: a Unix socket's path is limited to about 100 characters."""
    with tempfile.TemporaryDirectory(prefix="hs-") as directory:
        yield Path(directory)


@pytest.fixture
def machine(tmp_path: Path, socket_dir: Path) -> TemporaryMachine:
    """A sandbox before its first launch: sudo works, su doesn't, Docker's socket is the agent's group's."""
    machine_dir = tmp_path / "machine"
    bin_dir = machine_dir / "usr" / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python3.14"
    python.write_text("")
    python.chmod(0o755)
    (bin_dir / "python3").symlink_to("python3.14")
    passwd, passwd_log = recording_stand_in(machine_dir, "passwd")
    docker_socket = make_socket(socket_dir / "docker.sock", 0o660)
    owners: dict[Path, int] = {}
    return TemporaryMachine(
        root_mode=harden.Machine(
            managed_settings=machine_dir / "etc" / "claude-code" / "managed-settings.json",
            docker_daemon_config=machine_dir / "etc" / "docker" / "daemon.json",
            regrouped_socket=docker_socket,
            checked_sockets=(docker_socket, socket_dir / "containerd.sock"),
            python=str(bin_dir / "python3"),
            sudo=stand_in(bin_dir, "sudo", 0),
            su=stand_in(bin_dir, "su", 1),
            passwd=passwd,
            root_owner=ME,
            euid=lambda: 0,
            can_write=other_can_write,
            owner_of=lambda path: owners.get(path, ME.uid),
        ),
        dir=machine_dir,
        passwd_log=passwd_log,
        owners=owners,
    )


@pytest.fixture
def read_only_kit(tmp_path: Path, machine: TemporaryMachine) -> Iterator[Path]:
    """A copy of the real agent kit, its role skills' links included, with nothing in it writable. Its managed
    settings run the hooks through this machine's link, as the real ones do through the real machine's."""
    kit = tmp_path / "agent-kit"
    shutil.copytree(AGENT_KIT_SOURCE, kit, symlinks=True, ignore=shutil.ignore_patterns(".build"))
    settings = AgentKit(kit).managed_settings
    real_link, machine_link = str(harden.SANDBOX.hooks_runtime_link), str(machine.root_mode.hooks_runtime_link)
    assert real_link in settings.read_text()
    settings.write_text(settings.read_text().replace(real_link, machine_link))
    with read_only(kit):
        yield kit


@pytest.fixture
def hardened(machine: TemporaryMachine, read_only_kit: Path) -> TemporaryMachine:
    """The machine after root mode's first launch."""
    harden.harden(read_only_kit, SUDO_USER, machine.root_mode)
    return machine


@pytest.fixture
def refused(read_only_kit: Path, hardened: TemporaryMachine) -> Callable[..., None]:
    """assert_refused, on the hardened machine as the agent sees it."""
    return functools.partial(assert_refused, read_only_kit, hardened.agent_mode)
