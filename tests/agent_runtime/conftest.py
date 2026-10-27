"""Fixtures for the runtime's in-process tests: a temporary machine to harden, and a kit to harden it with."""

import dataclasses
import functools
import shutil
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from agent_runtime import contract, harden, session_setup
from agent_runtime.agent_kit import AgentKit
from foundry.session import SessionVariables
from foundry.task import Task
from tests.support import AGENT_KIT_SOURCE, TASK, SessionFor
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


@pytest.fixture
def session_for(tmp_path: Path, session_variables: Callable[[Task], SessionVariables]) -> SessionFor:
    """The session a sandbox for TASK gets, as foundry sets it, with the kit and the local origin given, and
    checkouts under tmp_path/work."""

    def make(agent_kit_dir: Path, origin: Path) -> contract.Environ:
        variables = dataclasses.replace(
            session_variables(TASK),
            agent_kit_dir=agent_kit_dir,
            project_dir=str(tmp_path / "work" / "p"),
            repo_url=f"file://{origin}",
        )
        return contract.read_environ(variables.to_env())

    return make


@pytest.fixture
def checkouts(
    session_for: SessionFor, built_kit: Path, created_task: Path, git_identity: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[contract.Environ, Path, Path]:
    """(the session, its code checkout, its notes checkout), set up by session_setup from a created task's origin,
    both clean and pushed. Commits aren't signed: the role signs with a key there is no private half of here, so
    signing is turned off by git's environment override, which beats any file."""
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, git_identity)
    for name, value in {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "commit.gpgsign",
        "GIT_CONFIG_VALUE_0": "false",
    }.items():
        monkeypatch.setenv(name, value)
    return session, session.agent_project_dir, session.agent_notes_dir
