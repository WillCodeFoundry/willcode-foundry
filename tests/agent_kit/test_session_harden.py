"""agent-kit/bin/session-harden: its refusal to run outside a sandbox, its verify mode's refusal to run
as root, and the checks in agent-kit/lib/hardening.sh that `session-harden --verify` runs.

Root mode removes sudo from the machine it runs on, so it is only run as far as its refusal. The
checks are run against sockets, files and stand-in commands of each test's own.
"""

import os
import socket
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
SESSION_HARDEN = AGENT_KIT_PATH / "bin" / "session-harden"
HARDENING_LIB = AGENT_KIT_PATH / "lib" / "hardening.sh"
KIT_SETTINGS = AGENT_KIT_PATH / "claude" / "managed-settings.json"

needs_non_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root can write to anything, so write permissions can't be checked as root"
)


@pytest.mark.parametrize("sudo_user", [None, "root", "will"])
def test_session_harden_refuses_outside_a_sandbox_before_changing_anything(sudo_user: str | None) -> None:
    # Never run with SUDO_USER=agent: as root, that would harden this machine.
    env = {"PATH": os.environ["PATH"], "AGENT_KIT_DIR": str(AGENT_KIT_PATH)}
    if sudo_user is not None:
        env["SUDO_USER"] = sudo_user
    result = subprocess.run([str(SESSION_HARDEN)], env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "only runs inside a foundry sandbox" in result.stderr


def test_session_harden_refuses_an_unknown_mode() -> None:
    env = {"PATH": os.environ["PATH"], "AGENT_KIT_DIR": str(AGENT_KIT_PATH)}
    result = subprocess.run([str(SESSION_HARDEN), "--fix"], env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "usage: session-harden [--verify]" in result.stderr


@pytest.mark.skipif(os.geteuid() != 0, reason="checks the refusal to verify as root")
def test_verify_refuses_to_run_as_root() -> None:
    env = {"PATH": os.environ["PATH"], "AGENT_KIT_DIR": str(AGENT_KIT_PATH)}
    result = subprocess.run([str(SESSION_HARDEN), "--verify"], env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "runs as the agent" in result.stderr


@needs_non_root
def test_verify_on_a_machine_that_isnt_a_hardened_sandbox_refuses_to_start_the_agent() -> None:
    """This machine has no managed settings installed, whatever else it allows."""
    env = {"PATH": os.environ["PATH"], "AGENT_KIT_DIR": str(AGENT_KIT_PATH)}
    result = subprocess.run([str(SESSION_HARDEN), "--verify"], env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "not starting the agent" in result.stderr
    assert "managed settings" in result.stderr


# --- the checks ---------------------------------------------------------------------


def run_check(check: str, *args: str, bin_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run one check from lib/hardening.sh; ``bin_dir``'s commands come first on PATH."""
    path = os.environ["PATH"] if bin_dir is None else f"{bin_dir}:{os.environ['PATH']}"
    return subprocess.run(
        ["bash", "-c", 'source "$0"; "$@"', str(HARDENING_LIB), check, *args],
        env={"PATH": path},
        capture_output=True,
        text=True,
        check=False,
    )


def stand_ins(tmp_path: Path, **exit_codes: int) -> Path:
    """A directory of commands that only exit with the code given, e.g. stand_ins(tmp_path, sudo=0)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, exit_code in exit_codes.items():
        command = bin_dir / name
        command.write_text(f"#!/bin/sh\nexit {exit_code}\n")
        command.chmod(0o755)
    return bin_dir


@pytest.mark.parametrize(("command", "check", "found"), [("sudo", "sudo", "run sudo"), ("su", "su", "su to root")])
def test_a_command_that_still_reaches_root_fails_its_check(
    tmp_path: Path, command: str, check: str, found: str
) -> None:
    result = run_check(f"hardening_check_{check}", bin_dir=stand_ins(tmp_path, **{command: 0}))

    assert result.returncode == 1
    assert result.stdout.strip() == found


@pytest.mark.parametrize("check", ["sudo", "su"])
def test_a_command_that_fails_passes_its_check(tmp_path: Path, check: str) -> None:
    result = run_check(f"hardening_check_{check}", bin_dir=stand_ins(tmp_path, **{check: 1}))

    assert (result.returncode, result.stdout) == (0, "")


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


@needs_non_root
def test_a_socket_the_agent_can_write_fails_naming_it(socket_dir: Path) -> None:
    open_socket = make_socket(socket_dir / "open.sock", 0o666)
    closed_socket = make_socket(socket_dir / "closed.sock", 0o600)
    closed_socket.chmod(0o000)  # owned by the test's user, so only no permissions at all keeps it out

    result = run_check("hardening_check_docker_sockets", str(closed_socket), str(open_socket))

    assert result.returncode == 1
    assert result.stdout.strip() == f"use {open_socket}, which is root over this sandbox"


@needs_non_root
def test_sockets_the_agent_cant_write_or_that_are_absent_pass(socket_dir: Path) -> None:
    closed_socket = make_socket(socket_dir / "closed.sock", 0o000)

    result = run_check("hardening_check_docker_sockets", str(closed_socket), str(socket_dir / "absent.sock"))

    assert (result.returncode, result.stdout) == (0, "")


def test_every_writable_socket_is_named_in_one_run(socket_dir: Path) -> None:
    if os.geteuid() != 0:
        sockets = [make_socket(socket_dir / f"{name}.sock", 0o666) for name in ("a", "b")]
    else:  # root can write to both, whatever their mode
        sockets = [make_socket(socket_dir / f"{name}.sock", 0o600) for name in ("a", "b")]

    result = run_check("hardening_check_docker_sockets", *map(str, sockets))

    assert result.returncode == 1
    assert result.stdout.splitlines() == [f"use {path}, which is root over this sandbox" for path in sockets]


@pytest.fixture
def installed_settings(tmp_path: Path) -> Path:
    """The kit's managed settings, installed read-only, owned by the test's user."""
    installed = tmp_path / "managed-settings.json"
    installed.write_bytes(KIT_SETTINGS.read_bytes())
    installed.chmod(0o444)
    return installed


def check_settings(installed: Path, owner: int | None = None) -> subprocess.CompletedProcess[str]:
    owner_uid = os.geteuid() if owner is None else owner
    return run_check("hardening_check_managed_settings", str(installed), str(KIT_SETTINGS), str(owner_uid))


@needs_non_root
def test_the_kits_settings_owned_and_read_only_pass(installed_settings: Path) -> None:
    result = check_settings(installed_settings)

    assert (result.returncode, result.stdout) == (0, "")


def test_missing_settings_fail(tmp_path: Path) -> None:
    result = check_settings(tmp_path / "managed-settings.json")

    assert result.returncode == 1
    assert "is missing" in result.stdout


def test_settings_owned_by_someone_else_fail(installed_settings: Path) -> None:
    result = check_settings(installed_settings, owner=os.geteuid() + 1)

    assert result.returncode == 1
    assert f"isn't owned by uid {os.geteuid() + 1}" in result.stdout


def test_settings_the_agent_can_write_fail(installed_settings: Path) -> None:
    installed_settings.chmod(installed_settings.stat().st_mode | stat.S_IWUSR)

    result = check_settings(installed_settings)

    assert result.returncode == 1
    assert "is writable" in result.stdout


@needs_non_root
def test_settings_from_an_older_kit_fail(installed_settings: Path) -> None:
    installed_settings.chmod(0o644)
    installed_settings.write_text('{"permissions": {}}\n')
    installed_settings.chmod(0o444)

    result = check_settings(installed_settings)

    assert result.returncode == 1
    assert f"differs from {KIT_SETTINGS}" in result.stdout


def test_the_root_owner_is_the_default(installed_settings: Path) -> None:
    result = run_check("hardening_check_managed_settings", str(installed_settings), str(KIT_SETTINGS))

    if os.geteuid() == 0:  # owned by root, but root can write it
        assert "is writable" in result.stdout
    else:
        assert "isn't owned by uid 0" in result.stdout
