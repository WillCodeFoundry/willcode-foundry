"""agent_runtime.harden: its refusals, the root mode's file steps, and the checks `harden --verify` runs.

Root mode removes sudo from the machine it runs on, so it is only run as far as its refusal; its file steps
are run against a temporary directory, owned by the test's user. chmod of sudo and `passwd -l` stay untested.
The checks are run against sockets, files and stand-in commands of each test's own.
"""

import contextlib
import dataclasses
import os
import shutil
import socket
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent_runtime import contract, harden

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
KIT_SETTINGS = harden.kit_settings(AGENT_KIT_PATH)
ME = harden.Owner(os.getuid(), os.getgid())
SOMEONE_ELSE = harden.Owner(os.getuid() + 1, os.getgid())

needs_non_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root can write to anything, so write permissions can't be checked as root"
)


# --- helpers -------------------------------------------------------------------------


@pytest.fixture
def socket_dir() -> Iterator[Path]:
    """A short directory: a Unix socket's path is limited to about 100 characters."""
    with tempfile.TemporaryDirectory(prefix="hs-") as directory:
        yield Path(directory)


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


# --- the real machine ----------------------------------------------------------------


def test_the_sandbox_is_the_real_machine(tmp_path: Path) -> None:
    """The paths, commands and access hardening acts on in a real sandbox, spelled out once more here, so a
    refactor can't change one silently."""
    sandbox = harden.SANDBOX

    assert sandbox.managed_settings == Path("/etc/claude-code/managed-settings.json")
    assert sandbox.docker_daemon_config == Path("/etc/docker/daemon.json")
    assert sandbox.regrouped_socket == Path("/var/run/docker.sock")
    assert sandbox.checked_sockets == (
        Path("/var/run/docker.sock"),
        Path("/var/run/docker/containerd/containerd.sock"),
    )
    assert sandbox.python == "/usr/bin/python3" == contract.PYTHON
    assert (sandbox.sudo, sandbox.su, sandbox.passwd) == ("sudo", "su", "passwd")
    assert sandbox.root == harden.Owner(0, 0)
    assert sandbox.euid is os.geteuid
    writable, read_only = tmp_path / "writable", tmp_path / "read-only"
    writable.write_text("")
    read_only.write_text("")
    read_only.chmod(0o444)
    for path in (writable, read_only, tmp_path / "absent"):
        assert sandbox.can_write(path) == os.access(path, os.W_OK), path


# --- a temporary machine: the second adapter behind harden.Machine ------------------------
#
# The agent is modelled as a user who is neither the owner nor in the group of what it touches: it can write
# a path when the path's "other" bits say so (for a link, its target's). In a test the root owner and the agent
# are the same user, so os.access would report every file root mode installs as writable.

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

    @property
    def agent_mode(self) -> harden.Machine:
        """The same machine as the agent sees it."""
        return dataclasses.replace(self.root_mode, euid=lambda: AGENT_UID)


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
            root=ME,
            euid=lambda: 0,
            can_write=other_can_write,
        ),
        dir=machine_dir,
        passwd_log=passwd_log,
    )


@pytest.fixture
def read_only_kit(tmp_path: Path) -> Iterator[Path]:
    """A copy of the real agent kit, its role skills' links included, with nothing in it writable."""
    kit = tmp_path / "agent-kit"
    shutil.copytree(AGENT_KIT_PATH, kit, symlinks=True, ignore=shutil.ignore_patterns(".build"))
    with read_only(kit):
        yield kit


def test_root_mode_then_agent_mode_on_one_machine(
    machine: TemporaryMachine, read_only_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """What the first launch does: harden as root, then verify as the agent, on the same files."""
    assert harden.harden(read_only_kit, "agent", machine.root_mode) == 0
    assert harden.verify(read_only_kit, machine.agent_mode) == 0
    assert capsys.readouterr().out.endswith("harden --verify: hardened\n")

    root_mode = machine.root_mode
    installed = root_mode.managed_settings
    assert installed.read_bytes() == (read_only_kit / "claude" / "managed-settings.json").read_bytes()
    assert stat.S_IMODE(installed.stat().st_mode) == 0o644
    assert (installed.stat().st_uid, installed.stat().st_gid) == root_mode.root
    assert stat.S_IMODE(installed.parent.stat().st_mode) == 0o755
    assert [path.name for path in installed.parent.iterdir()] == [installed.name]  # no partial file left
    assert root_mode.docker_daemon_config.read_text() == '{"group": "root"}\n'
    assert stat.S_IMODE(root_mode.docker_daemon_config.stat().st_mode) == 0o644
    assert root_mode.regrouped_socket.stat().st_gid == root_mode.root.gid
    assert stat.S_IMODE(Path(root_mode.sudo).stat().st_mode) == 0
    assert machine.passwd_log.read_text() == "-l root\n"


# --- agent mode: each way the agent could still reach root makes verify refuse --------------
#
# Each case starts from a machine root mode has just hardened, breaks one thing, and checks verify refuses,
# naming it in today's words.


@pytest.fixture
def hardened(machine: TemporaryMachine, read_only_kit: Path, capsys: pytest.CaptureFixture[str]) -> TemporaryMachine:
    """The machine after root mode's first launch, its output discarded."""
    assert harden.harden(read_only_kit, "agent", machine.root_mode) == 0
    capsys.readouterr()
    return machine


def assert_refused(
    capsys: pytest.CaptureFixture[str], kit: Path, machine: harden.Machine, *lines: str, startswith: str = ""
) -> None:
    """verify refuses to start the agent, and says each of ``lines``, one line each."""
    assert harden.verify(kit, machine) == 1
    err = capsys.readouterr().err
    assert "not starting the agent" in err
    found = [line.removeprefix("  ") for line in err.splitlines()]
    for line in lines:
        assert line in found, err
    if startswith:
        assert any(line.startswith(startswith) for line in found), err


@contextlib.contextmanager
def writable(directory: Path) -> Iterator[None]:
    """Let the test, as the kit's owner, add something to a read-only folder of it."""
    directory.chmod(0o755)
    try:
        yield
    finally:
        directory.chmod(0o555)


def test_missing_settings_are_refused(hardened, read_only_kit, capsys) -> None:
    installed = hardened.root_mode.managed_settings
    installed.unlink()

    assert_refused(
        capsys, read_only_kit, hardened.agent_mode, f"run without Claude's managed settings: {installed} is missing"
    )


def test_settings_and_interpreter_root_doesnt_own_are_refused(hardened, read_only_kit, capsys) -> None:
    """A non-root test can't give a file away, so the machine's root becomes someone else instead."""
    agent_mode = dataclasses.replace(hardened.agent_mode, root=SOMEONE_ELSE)
    installed = agent_mode.managed_settings
    python = Path(agent_mode.python)

    assert_refused(
        capsys,
        read_only_kit,
        agent_mode,
        f"replace Claude's managed settings: {installed} isn't owned by uid {SOMEONE_ELSE.uid}",
        f"replace the hooks' interpreter: {python} (resolving to {python.resolve()})"
        f" isn't owned by uid {SOMEONE_ELSE.uid}",
    )


def test_settings_the_agent_can_write_are_refused(hardened, read_only_kit, capsys) -> None:
    installed = hardened.root_mode.managed_settings
    installed.chmod(0o646)

    assert_refused(
        capsys, read_only_kit, hardened.agent_mode, f"change Claude's managed settings: {installed} is writable"
    )


def test_settings_other_than_the_kits_are_refused(hardened, read_only_kit, capsys) -> None:
    installed = hardened.root_mode.managed_settings
    installed.write_text('{"permissions": {}}\n')
    kit_copy = read_only_kit / "claude" / "managed-settings.json"

    assert_refused(
        capsys,
        read_only_kit,
        hardened.agent_mode,
        f"run with older managed settings: {installed} differs from {kit_copy}",
    )


@pytest.mark.parametrize(("command", "line"), [("sudo", "run sudo"), ("su", "su to root")])
def test_a_command_that_still_reaches_root_is_refused(hardened, read_only_kit, capsys, command: str, line: str) -> None:
    stand_in_path = Path(getattr(hardened.agent_mode, command))
    stand_in(stand_in_path.parent, stand_in_path.name, 0)

    assert_refused(capsys, read_only_kit, hardened.agent_mode, line)


def test_every_docker_socket_the_agent_can_write_is_named_in_one_run(hardened, read_only_kit, capsys) -> None:
    docker_socket, containerd_socket = hardened.agent_mode.checked_sockets
    docker_socket.chmod(0o666)
    make_socket(containerd_socket, 0o666)

    assert_refused(
        capsys,
        read_only_kit,
        hardened.agent_mode,
        f"use {docker_socket}, which is root over this sandbox",
        f"use {containerd_socket}, which is root over this sandbox",
    )


def test_a_writable_file_in_the_kit_is_refused(hardened, read_only_kit, capsys) -> None:
    agents_md = read_only_kit / "AGENTS.md"
    agents_md.chmod(0o446)

    assert_refused(capsys, read_only_kit, hardened.agent_mode, f"change the agent kit: {agents_md} is writable")


def test_a_link_to_a_writable_folder_outside_the_kit_is_refused(hardened, read_only_kit, tmp_path, capsys) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o777)
    link = read_only_kit / "hooks" / "outside"
    with writable(link.parent):
        link.symlink_to(outside)

    assert_refused(capsys, read_only_kit, hardened.agent_mode, f"change the agent kit: {link} is writable")


def test_a_link_to_nothing_in_the_kit_is_refused(hardened, read_only_kit, tmp_path, capsys) -> None:
    link = read_only_kit / "hooks" / "nowhere"
    with writable(link.parent):
        link.symlink_to(tmp_path / "nothing")

    assert_refused(
        capsys,
        read_only_kit,
        hardened.agent_mode,
        f"change the agent kit: {link} links to {tmp_path / 'nothing'}, which doesn't exist",
    )


@needs_non_root
def test_a_kit_folder_that_cant_be_listed_is_refused(hardened, read_only_kit, capsys) -> None:
    """Listing is real: root can list anything, so this runs as another user only."""
    hooks = read_only_kit / "hooks"
    hooks.chmod(0o000)
    try:
        assert_refused(
            capsys,
            read_only_kit,
            hardened.agent_mode,
            startswith=f"change the agent kit unchecked: {hooks} can't be listed",
        )
    finally:
        hooks.chmod(0o555)


def test_a_missing_kit_is_refused(hardened, tmp_path, capsys) -> None:
    assert harden.verify(tmp_path / "absent", hardened.agent_mode) == 1
    err = capsys.readouterr().err
    assert "not starting the agent" in err and "can't be listed" in err


def test_a_missing_interpreter_is_refused(hardened, read_only_kit, capsys) -> None:
    python = Path(hardened.agent_mode.python)
    python.resolve().unlink()

    assert harden.verify(read_only_kit, hardened.agent_mode) == 1
    err = capsys.readouterr().err
    assert "not starting the agent" in err
    assert any(
        line.startswith("  run without the hooks' interpreter:") and "is missing" in line for line in err.splitlines()
    )


def test_an_interpreter_the_agent_can_write_is_refused(hardened, read_only_kit, capsys) -> None:
    python = Path(hardened.agent_mode.python)
    python.resolve().chmod(0o757)

    assert_refused(
        capsys,
        read_only_kit,
        hardened.agent_mode,
        f"change the hooks' interpreter: {python} (resolving to {python.resolve()}) is writable",
    )


@pytest.mark.parametrize("sudo", ["missing", "failing", "unexecutable"])
def test_a_sudo_that_cant_reach_root_passes(hardened, read_only_kit, tmp_path, capsys, sudo: str) -> None:
    """Unexecutable is what root mode leaves, and what every later launch finds (review finding R12)."""
    agent_mode = hardened.agent_mode
    if sudo == "missing":
        agent_mode = dataclasses.replace(agent_mode, sudo=str(tmp_path / "absent"))
    elif sudo == "failing":
        stand_in(Path(agent_mode.sudo).parent, "sudo", 1)

    assert harden.verify(read_only_kit, agent_mode) == 0, capsys.readouterr().err


def test_a_missing_su_passes(hardened, read_only_kit, tmp_path, capsys) -> None:
    agent_mode = dataclasses.replace(hardened.agent_mode, su=str(tmp_path / "absent"))

    assert harden.verify(read_only_kit, agent_mode) == 0, capsys.readouterr().err


def test_verify_refuses_to_run_as_root(hardened, read_only_kit, capsys) -> None:
    """It checks what the agent can do; root can do anything."""
    assert harden.verify(read_only_kit, hardened.root_mode) == 1
    assert "runs as the agent" in capsys.readouterr().err


# --- root mode: what it changes, in what order, and what it refuses -----------------------


def snapshot(machine: TemporaryMachine) -> dict[str, tuple[object, ...]]:
    """Everything on the machine: each path's mode, owner and contents, or link target, and its sockets'."""
    root_mode = machine.root_mode
    paths = [*sorted(machine.dir.rglob("*")), *root_mode.checked_sockets]
    state: dict[str, tuple[object, ...]] = {}
    for path in paths:
        if path.is_symlink():
            state[str(path)] = ("link", os.readlink(path))
        elif path.exists():
            status = path.lstat()
            content = path.read_bytes() if path.is_file() and status.st_mode & stat.S_IRUSR else None
            state[str(path)] = (status.st_mode, status.st_uid, status.st_gid, content)
    return state


@pytest.mark.parametrize("sudo_user", ["", "root", "will"])
def test_root_mode_refuses_outside_a_sandbox_changing_nothing(
    machine: TemporaryMachine, read_only_kit: Path, capsys: pytest.CaptureFixture[str], sudo_user: str
) -> None:
    """Removing sudo would lock a real machine's owner out: only sudo from the sandbox's agent may run it."""
    before = snapshot(machine)

    assert harden.harden(read_only_kit, sudo_user, machine.root_mode) == 1

    err = capsys.readouterr().err
    assert "only runs inside a foundry sandbox" in err and f"(SUDO_USER is '{sudo_user or 'unset'}')" in err
    assert snapshot(machine) == before


def test_root_mode_refuses_without_root_changing_nothing(
    machine: TemporaryMachine, read_only_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = snapshot(machine)

    assert harden.harden(read_only_kit, "agent", machine.agent_mode) == 1

    err = capsys.readouterr().err
    assert "only runs inside a foundry sandbox" in err and "(SUDO_USER is 'agent')" in err
    assert snapshot(machine) == before


def test_settings_from_an_older_kit_are_replaced(machine: TemporaryMachine, read_only_kit: Path) -> None:
    installed = machine.root_mode.managed_settings
    installed.parent.mkdir(parents=True)
    installed.write_text('{"permissions": {}}\n')
    installed.chmod(0o600)

    assert harden.harden(read_only_kit, "agent", machine.root_mode) == 0

    assert installed.read_bytes() == (read_only_kit / "claude" / "managed-settings.json").read_bytes()
    assert stat.S_IMODE(installed.stat().st_mode) == 0o644


def test_dockers_configuration_from_an_earlier_launch_is_kept(machine: TemporaryMachine, read_only_kit: Path) -> None:
    daemon_config = machine.root_mode.docker_daemon_config
    daemon_config.parent.mkdir(parents=True)
    daemon_config.write_text('{"group": "root"}\n')

    assert harden.harden(read_only_kit, "agent", machine.root_mode) == 0

    assert daemon_config.read_text() == '{"group": "root"}\n'


def test_a_templates_own_docker_configuration_is_refused_after_the_other_steps(
    machine: TemporaryMachine, read_only_kit: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Docker comes last: the settings and sudo steps have run when it refuses, and its own file is untouched."""
    daemon_config = machine.root_mode.docker_daemon_config
    daemon_config.parent.mkdir(parents=True)
    daemon_config.write_text('{"debug": true}\n')

    assert harden.harden(read_only_kit, "agent", machine.root_mode) == 1

    err = capsys.readouterr().err
    assert "harden: refusing:" in err and "already has" in err
    assert daemon_config.read_text() == '{"debug": true}\n'
    assert machine.root_mode.managed_settings.is_file()  # step 1 ran
    assert machine.passwd_log.read_text() == "-l root\n"  # step 2 ran


def test_a_sudo_that_cant_be_found_is_refused_after_the_settings_and_before_docker(
    machine: TemporaryMachine, read_only_kit: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """sudo and su come second: the settings are installed when it refuses; passwd and Docker are left alone."""
    root_mode = dataclasses.replace(machine.root_mode, sudo=str(tmp_path / "absent"))

    assert harden.harden(read_only_kit, "agent", root_mode) == 1

    assert "harden: refusing: can't find" in capsys.readouterr().err
    assert root_mode.managed_settings.is_file()  # step 1 ran
    assert not machine.passwd_log.exists()
    assert not root_mode.docker_daemon_config.exists()  # step 3 didn't
