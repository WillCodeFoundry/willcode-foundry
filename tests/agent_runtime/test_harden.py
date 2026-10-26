"""agent_runtime.harden: its refusals, the root mode's file steps, and the checks `harden --verify` runs.

Root mode removes sudo from the machine it runs on, so it is only run as far as its refusal; its file steps
are run against a temporary directory, owned by the test's user. chmod of sudo and `passwd -l` stay untested.
The checks are run against sockets, files and stand-in commands of each test's own.
"""

import contextlib
import os
import socket
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent_runtime import harden

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
KIT_SETTINGS = harden.kit_settings(AGENT_KIT_PATH)
ME = harden.Owner(os.getuid(), os.getgid())
SOMEONE_ELSE = harden.Owner(os.getuid() + 1, os.getgid())

needs_non_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root can write to anything, so write permissions can't be checked as root"
)


# --- the two modes' refusals ---------------------------------------------------------


@pytest.mark.parametrize("sudo_user", ["", "root", "will"])
def test_harden_refuses_outside_a_sandbox_before_changing_anything(
    capsys: pytest.CaptureFixture[str], sudo_user: str
) -> None:
    # Never with SUDO_USER=agent: as root, that would harden this machine.
    assert harden.harden(AGENT_KIT_PATH, sudo_user) == 1
    assert "only runs inside a foundry sandbox" in capsys.readouterr().err


@pytest.mark.skipif(os.geteuid() != 0, reason="checks the refusal to verify as root")
def test_verify_refuses_to_run_as_root(capsys: pytest.CaptureFixture[str]) -> None:
    assert harden.verify(AGENT_KIT_PATH) == 1
    assert "runs as the agent" in capsys.readouterr().err


@needs_non_root
def test_verify_on_a_machine_that_isnt_a_hardened_sandbox_refuses_to_start_the_agent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """This machine has no managed settings installed, whatever else it allows."""
    assert harden.verify(AGENT_KIT_PATH) == 1
    err = capsys.readouterr().err
    assert "not starting the agent" in err
    assert "managed settings" in err


# --- root mode's file steps ----------------------------------------------------------


def test_the_kits_settings_are_installed_read_only_for_others(tmp_path: Path) -> None:
    installed = tmp_path / "etc" / "claude-code" / "managed-settings.json"

    harden.harden_managed_settings(KIT_SETTINGS, installed, owner=ME)

    assert installed.read_bytes() == KIT_SETTINGS.read_bytes()
    assert stat.S_IMODE(installed.stat().st_mode) == 0o644
    assert stat.S_IMODE(installed.parent.stat().st_mode) == 0o755
    assert (installed.stat().st_uid, installed.stat().st_gid) == ME
    assert [path.name for path in installed.parent.iterdir()] == [installed.name]  # no partial file left


def test_installing_replaces_settings_from_an_older_kit(tmp_path: Path) -> None:
    installed = tmp_path / "managed-settings.json"
    installed.write_text('{"permissions": {}}\n')
    installed.chmod(0o600)

    harden.harden_managed_settings(KIT_SETTINGS, installed, owner=ME)

    assert installed.read_bytes() == KIT_SETTINGS.read_bytes()
    assert stat.S_IMODE(installed.stat().st_mode) == 0o644


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


def test_docker_is_configured_to_give_its_socket_to_root(tmp_path: Path, socket_dir: Path) -> None:
    daemon_config = tmp_path / "etc" / "docker" / "daemon.json"
    docker_socket = make_socket(socket_dir / "docker.sock", 0o660)

    harden.harden_docker(daemon_config, [docker_socket, socket_dir / "absent.sock"], owner=ME)

    assert daemon_config.read_text() == '{"group": "root"}\n'
    assert stat.S_IMODE(daemon_config.stat().st_mode) == 0o644
    assert docker_socket.stat().st_gid == ME.gid


def test_dockers_configuration_from_an_earlier_launch_is_kept(tmp_path: Path) -> None:
    daemon_config = tmp_path / "daemon.json"
    daemon_config.write_text('{"group": "root"}\n')

    harden.harden_docker(daemon_config, [], owner=ME)

    assert daemon_config.read_text() == '{"group": "root"}\n'


def test_a_templates_own_docker_configuration_is_refused_untouched(tmp_path: Path) -> None:
    daemon_config = tmp_path / "daemon.json"
    daemon_config.write_text('{"debug": true}\n')

    with pytest.raises(harden.HardenError, match="already has"):
        harden.harden_docker(daemon_config, [], owner=ME)

    assert daemon_config.read_text() == '{"debug": true}\n'


# --- the checks ----------------------------------------------------------------------


def stand_in(tmp_path: Path, name: str, exit_code: int) -> str:
    """A command that only exits with the code given."""
    command = tmp_path / name
    command.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    command.chmod(0o755)
    return str(command)


@pytest.mark.parametrize(("check", "found"), [(harden.check_sudo, "run sudo"), (harden.check_su, "su to root")])
def test_a_command_that_still_reaches_root_fails_its_check(tmp_path: Path, check, found: str) -> None:
    assert check(stand_in(tmp_path, "command", 0)) == [found]


@pytest.mark.parametrize("check", [harden.check_sudo, harden.check_su])
def test_a_command_that_fails_or_is_missing_passes_its_check(tmp_path: Path, check) -> None:
    assert check(stand_in(tmp_path, "command", 1)) == []
    assert check(str(tmp_path / "absent")) == []


@needs_non_root
def test_a_socket_the_agent_can_write_fails_naming_it(socket_dir: Path) -> None:
    open_socket = make_socket(socket_dir / "open.sock", 0o666)
    closed_socket = make_socket(socket_dir / "closed.sock", 0o600)
    closed_socket.chmod(0o000)  # owned by the test's user, so only no permissions at all keeps it out

    assert harden.check_docker_sockets([closed_socket, open_socket]) == [
        f"use {open_socket}, which is root over this sandbox"
    ]


@needs_non_root
def test_sockets_the_agent_cant_write_or_that_are_absent_pass(socket_dir: Path) -> None:
    closed_socket = make_socket(socket_dir / "closed.sock", 0o000)

    assert harden.check_docker_sockets([closed_socket, socket_dir / "absent.sock"]) == []


def test_every_writable_socket_is_named_in_one_run(socket_dir: Path) -> None:
    mode = 0o666 if os.geteuid() != 0 else 0o600  # root can write to both, whatever their mode
    sockets = [make_socket(socket_dir / f"{name}.sock", mode) for name in ("a", "b")]

    assert harden.check_docker_sockets(sockets) == [f"use {path}, which is root over this sandbox" for path in sockets]


@pytest.fixture
def installed_settings(tmp_path: Path) -> Path:
    """The kit's managed settings, installed read-only, owned by the test's user."""
    installed = tmp_path / "managed-settings.json"
    installed.write_bytes(KIT_SETTINGS.read_bytes())
    installed.chmod(0o444)
    return installed


@needs_non_root
def test_the_kits_settings_owned_and_read_only_pass(installed_settings: Path) -> None:
    assert harden.check_managed_settings(installed_settings, KIT_SETTINGS, ME) == []


def test_missing_settings_fail(tmp_path: Path) -> None:
    (found,) = harden.check_managed_settings(tmp_path / "managed-settings.json", KIT_SETTINGS, ME)
    assert "is missing" in found


def test_settings_owned_by_someone_else_fail(installed_settings: Path) -> None:
    (found,) = harden.check_managed_settings(installed_settings, KIT_SETTINGS, SOMEONE_ELSE)
    assert f"isn't owned by uid {os.geteuid() + 1}" in found


def test_settings_the_agent_can_write_fail(installed_settings: Path) -> None:
    installed_settings.chmod(installed_settings.stat().st_mode | stat.S_IWUSR)

    (found,) = harden.check_managed_settings(installed_settings, KIT_SETTINGS, ME)
    assert "is writable" in found


@needs_non_root
def test_settings_from_an_older_kit_fail(installed_settings: Path) -> None:
    installed_settings.chmod(0o644)
    installed_settings.write_text('{"permissions": {}}\n')
    installed_settings.chmod(0o444)

    (found,) = harden.check_managed_settings(installed_settings, KIT_SETTINGS, ME)
    assert f"differs from {KIT_SETTINGS}" in found


def test_the_root_owner_is_the_default(installed_settings: Path) -> None:
    (found,) = harden.check_managed_settings(installed_settings, KIT_SETTINGS)

    if os.geteuid() == 0:  # owned by root, but root can write it
        assert "is writable" in found
    else:
        assert "isn't owned by uid 0" in found


@pytest.fixture
def kit(tmp_path: Path) -> Path:
    kit = tmp_path / "agent-kit"
    (kit / "hooks").mkdir(parents=True)
    (kit / "hooks" / "pre-commit").write_text("#!/usr/bin/python3 -I\n")
    return kit


def test_a_kit_the_agent_can_write_fails(kit: Path) -> None:
    (found,) = harden.check_kit_read_only(kit)
    assert found == f"change the agent kit: {kit} is writable"


@needs_non_root
def test_one_writable_file_in_the_kit_fails_naming_it(kit: Path) -> None:
    for directory in (kit, kit / "hooks"):
        directory.chmod(0o555)
    try:
        assert harden.check_kit_read_only(kit) == [f"change the agent kit: {kit / 'hooks' / 'pre-commit'} is writable"]
        (kit / "hooks" / "pre-commit").chmod(0o444)
        assert harden.check_kit_read_only(kit) == []
    finally:
        for directory in (kit, kit / "hooks"):
            directory.chmod(0o755)


def test_an_interpreter_the_agent_owns_fails(tmp_path: Path) -> None:
    python = tmp_path / "python3"
    python.write_text("")
    link = tmp_path / "python"
    link.symlink_to(python)

    (found,) = harden.check_python(str(link), owner=SOMEONE_ELSE)
    assert found == (
        f"replace the hooks' interpreter: {link} (resolving to {python}) isn't owned by uid {SOMEONE_ELSE.uid}"
    )


def test_an_interpreter_the_agent_can_write_fails(tmp_path: Path) -> None:
    python = tmp_path / "python3"
    python.write_text("")
    python.chmod(0o755 if os.geteuid() != 0 else 0o555)  # root can write it either way

    (found,) = harden.check_python(str(python), owner=ME)
    assert found == f"change the hooks' interpreter: {python} (resolving to {python}) is writable"


@needs_non_root
def test_an_interpreter_owned_and_read_only_passes(tmp_path: Path) -> None:
    python = tmp_path / "python3"
    python.write_text("")
    python.chmod(0o555)

    assert harden.check_python(str(python), owner=ME) == []


def test_a_missing_interpreter_fails(tmp_path: Path) -> None:
    (found,) = harden.check_python(str(tmp_path / "python3"))
    assert "is missing" in found


def test_a_sudo_hardening_left_unexecutable_is_no_sudo_and_no_crash(tmp_path: Path) -> None:
    """Every launch after the first finds the sudo the first one left mode 0: session-init must go on to
    verify. Mode 0 keeps out even root, so this runs as any user."""
    sudo = Path(stand_in(tmp_path, "sudo", 0))
    sudo.chmod(0)

    assert harden.can_sudo(str(sudo)) is False
    assert harden.check_sudo(str(sudo)) == []


def test_a_sudo_that_cant_be_found_is_refused_before_changing_anything(tmp_path: Path) -> None:
    with pytest.raises(harden.HardenError, match="can't find"):
        harden.harden_sudo_and_su(str(tmp_path / "absent"))


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


@needs_non_root
def test_a_link_to_a_writable_target_outside_the_kit_fails(kit: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (kit / "hooks" / "link").symlink_to(outside)

    with read_only(kit):
        found = harden.check_kit_read_only(kit)

    assert found == [f"change the agent kit: {kit / 'hooks' / 'link'} is writable"]


@needs_non_root
def test_a_link_to_nothing_fails(kit: Path, tmp_path: Path) -> None:
    (kit / "hooks" / "link").symlink_to(tmp_path / "nothing")

    with read_only(kit):
        found = harden.check_kit_read_only(kit)

    assert found == [
        f"change the agent kit: {kit / 'hooks' / 'link'} links to {tmp_path / 'nothing'}, which doesn't exist"
    ]


@needs_non_root
def test_a_read_only_kit_with_links_inside_it_passes(kit: Path) -> None:
    (kit / "hooks" / "link").symlink_to("pre-commit")

    with read_only(kit):
        assert harden.check_kit_read_only(kit) == []


@needs_non_root
def test_a_folder_that_cant_be_listed_fails(kit: Path) -> None:
    with read_only(kit):
        (kit / "hooks").chmod(0o000)
        (found,) = harden.check_kit_read_only(kit)

    assert found.startswith(f"change the agent kit unchecked: {kit / 'hooks'} can't be listed")


def test_a_missing_kit_fails(tmp_path: Path) -> None:
    (found,) = harden.check_kit_read_only(tmp_path / "absent")
    assert "can't be listed" in found
