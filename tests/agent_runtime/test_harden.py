"""agent_runtime.harden, through its two modes, on a temporary machine instead of the real one.

Each test builds a harden.Machine of its own under tmp_path: managed settings, Docker configuration and
sockets, an interpreter, and stand-in sudo, su and passwd. The round trip runs root mode, then agent mode,
on the same files, as the first launch does. Every way the agent could still reach root is a case that
breaks one thing on a hardened machine and expects verify to refuse it; every refusal of root mode must
leave the machine as it found it.

chmod of sudo and `passwd -l` run against stand-ins: their effect on a real sandbox is checked only by a real
launch. The machine models the agent as a user who is neither owner nor in the group of what it touches, and
who owns each path (see TemporaryMachine), since in a test root and the agent are one user. No test hardens
the real machine: harden and verify are always given a temporary one, and SANDBOX is only checked against its
literal values.
"""

import dataclasses
import os
import stat
from pathlib import Path

import pytest

from agent_runtime import harden
from agent_runtime.agent_kit import PYTHON, AgentKit
from tests.support.machine import (
    AGENT_UID,
    ME,
    SOMEONE_ELSE,
    SUDO_USER,
    TemporaryMachine,
    assert_refused,
    make_socket,
    stand_in,
    writable,
)

# --- the real machine ----------------------------------------------------------------


def test_the_sandbox_is_the_real_machine(tmp_path: Path) -> None:
    """The paths, commands and access hardening acts on in a real sandbox, spelled out once more here, so a
    refactor can't change one silently."""
    sandbox = harden.SANDBOX

    assert sandbox.managed_settings == Path("/etc/claude-code/managed-settings.json")
    assert sandbox.hooks_runtime_link == Path("/etc/claude-code/agent_runtime.pyz")
    assert sandbox.docker_daemon_config == Path("/etc/docker/daemon.json")
    assert sandbox.regrouped_socket == Path("/var/run/docker.sock")
    assert sandbox.checked_sockets == (
        Path("/var/run/docker.sock"),
        Path("/var/run/docker/containerd/containerd.sock"),
    )
    assert sandbox.python == "/usr/bin/python3" == PYTHON
    assert (sandbox.sudo, sandbox.su, sandbox.passwd) == ("sudo", "su", "passwd")
    assert sandbox.root_owner == harden.Owner(0, 0)
    assert sandbox.euid is os.geteuid
    writable, read_only = tmp_path / "writable", tmp_path / "read-only"
    writable.write_text("")
    read_only.write_text("")
    read_only.chmod(0o444)
    for path in (writable, read_only, tmp_path / "absent"):
        assert sandbox.can_write(path) == os.access(path, os.W_OK), path
    for path in (writable, tmp_path):
        assert sandbox.owner_of(path) == path.stat().st_uid, path


def test_root_mode_then_agent_mode_on_one_machine(machine: TemporaryMachine, read_only_kit: Path) -> None:
    """What the first launch does: harden as root, then verify as the agent, on the same files."""
    harden.harden(read_only_kit, SUDO_USER, machine.root_mode)
    assert harden.verify(read_only_kit, machine.agent_mode) == []

    root_mode = machine.root_mode
    installed = root_mode.managed_settings
    assert installed.read_bytes() == (read_only_kit / "claude" / "managed-settings.json").read_bytes()
    assert stat.S_IMODE(installed.stat().st_mode) == 0o644
    assert (installed.stat().st_uid, installed.stat().st_gid) == root_mode.root_owner
    assert stat.S_IMODE(installed.parent.stat().st_mode) == 0o755
    # The settings and the link to the hooks' runtime, and no partial file left.
    assert sorted(path.name for path in installed.parent.iterdir()) == ["agent_runtime.pyz", installed.name]
    assert os.readlink(root_mode.hooks_runtime_link) == str(AgentKit(read_only_kit).runtime)
    assert root_mode.docker_daemon_config.read_text() == '{"group": "root"}\n'
    assert stat.S_IMODE(root_mode.docker_daemon_config.stat().st_mode) == 0o644
    assert root_mode.regrouped_socket.stat().st_gid == root_mode.root_owner.gid
    assert stat.S_IMODE(Path(root_mode.sudo).stat().st_mode) == 0
    assert machine.passwd_log.read_text() == "-l root\n"


def _two_groups() -> tuple[int, int] | None:
    """Two groups this user may give a file to, both its own; None if it has one."""
    groups = sorted(set(os.getgroups()) | {os.getgid()})
    return (groups[0], groups[1]) if len(groups) > 1 else None


def test_root_mode_gives_the_docker_socket_to_root(machine: TemporaryMachine, read_only_kit: Path) -> None:
    """The socket starts in the agent's group, as sbx's docker group, and ends in root's: the round trip can't
    show it, since there the two are the same. It is the only host test of that, so on CI, where the runner's
    user is in several groups, a user in one fails it rather than skips it unseen."""
    groups = _two_groups()
    if groups is None:
        needs = "needs a user in two groups, to start the socket in the other"
        if os.environ.get("CI"):
            pytest.fail(f"{needs}; CI's runner user used to be", pytrace=False)
        pytest.skip(needs)
    agents_group, roots_group = groups
    socket_path = machine.root_mode.regrouped_socket
    os.chown(socket_path, -1, agents_group)
    root_mode = dataclasses.replace(machine.root_mode, root_owner=harden.Owner(ME.uid, roots_group))

    harden.harden(read_only_kit, SUDO_USER, root_mode)

    assert socket_path.stat().st_gid == roots_group


# --- agent mode: each way the agent could still reach root makes verify refuse --------------
#
# Each case starts from a machine root mode has just hardened, breaks one thing, and checks verify refuses,
# naming it in today's words.


def test_missing_settings_are_refused(hardened, refused, read_only_kit) -> None:
    installed = hardened.root_mode.managed_settings
    installed.unlink()

    refused(f"run without Claude's managed settings: {installed} is missing")


def test_settings_root_doesnt_own_are_refused(hardened, refused, read_only_kit) -> None:
    installed = hardened.root_mode.managed_settings
    hardened.owners[installed] = SOMEONE_ELSE.uid

    refused(
        f"replace Claude's managed settings: {installed} isn't owned by uid {ME.uid}",
    )


def test_an_interpreter_root_doesnt_own_is_refused(hardened, refused, read_only_kit) -> None:
    python = Path(hardened.root_mode.python)
    hardened.owners[python.resolve()] = SOMEONE_ELSE.uid

    refused(
        f"replace the hooks' interpreter: {python} (resolving to {python.resolve()}) isn't owned by uid {ME.uid}",
    )


def test_settings_in_a_folder_root_doesnt_own_are_refused(hardened, refused, read_only_kit) -> None:
    """Whoever owns the folder can swap the settings in it during a session, whoever owns the file."""
    folder = hardened.root_mode.managed_settings.parent
    hardened.owners[folder] = SOMEONE_ELSE.uid

    refused(
        f"replace Claude's managed settings: {folder} isn't owned by uid {ME.uid}",
    )


def test_settings_in_a_folder_the_agent_can_write_are_refused(hardened, refused, read_only_kit) -> None:
    folder = hardened.root_mode.managed_settings.parent
    folder.chmod(0o757)

    refused(
        f"replace Claude's managed settings: {folder} is writable",
        f"replace the hooks' runtime: {folder} is writable",
    )


def test_a_missing_hooks_runtime_link_is_refused(hardened, refused, read_only_kit) -> None:
    """A sandbox hardened before the hooks found their runtime through the link."""
    link = hardened.root_mode.hooks_runtime_link
    link.unlink()

    refused(f"run Claude's hooks without their runtime: {link} is missing")


@pytest.mark.parametrize("replacement", ["link elsewhere", "file"])
def test_a_hooks_runtime_that_isnt_the_kits_is_refused(hardened, refused, read_only_kit, tmp_path, replacement) -> None:
    """The managed hooks run whatever this path holds."""
    link = hardened.root_mode.hooks_runtime_link
    link.unlink()
    if replacement == "file":
        link.write_bytes(b"")
    else:
        link.symlink_to(tmp_path / "agents-own.pyz")

    refused(
        f"run other code as Claude's hooks: {link} doesn't link to {AgentKit(read_only_kit).runtime}",
    )


def test_settings_the_agent_can_write_are_refused(hardened, refused, read_only_kit) -> None:
    installed = hardened.root_mode.managed_settings
    installed.chmod(0o646)

    refused(f"change Claude's managed settings: {installed} is writable")


def test_settings_whose_hooks_skip_the_link_are_refused(hardened, read_only_kit) -> None:
    """The settings match the kit, but a hook names the runtime some other way: the link proves nothing then."""
    link = str(hardened.root_mode.hooks_runtime_link)
    kit_settings = AgentKit(read_only_kit).managed_settings
    elsewhere = kit_settings.read_text().replace(f"{link} hook guard-bash", "$AGENT_KIT_DIR/x.pyz hook guard-bash")
    with writable(kit_settings.parent):
        kit_settings.chmod(0o644)
        kit_settings.write_text(elsewhere)
        kit_settings.chmod(0o444)
    hardened.root_mode.managed_settings.write_text(elsewhere)

    assert_refused(
        read_only_kit,
        hardened.agent_mode,
        f"run a hook that skips the runtime's link, {link}: /usr/bin/python3 -IS $AGENT_KIT_DIR/x.pyz hook guard-bash",
    )


def test_settings_other_than_the_kits_are_refused(hardened, refused, read_only_kit) -> None:
    installed = hardened.root_mode.managed_settings
    installed.write_text('{"permissions": {}}\n')
    kit_copy = read_only_kit / "claude" / "managed-settings.json"

    refused(
        f"run with older managed settings: {installed} differs from {kit_copy}",
    )


@pytest.mark.parametrize(("command", "line"), [("sudo", "run sudo"), ("su", "su to root")])
def test_a_command_that_still_reaches_root_is_refused(
    hardened, refused, read_only_kit, command: str, line: str
) -> None:
    stand_in_path = Path(getattr(hardened.agent_mode, command))
    stand_in(stand_in_path.parent, stand_in_path.name, 0)

    refused(line)


def test_every_docker_socket_the_agent_can_write_is_named_in_one_run(hardened, refused, read_only_kit) -> None:
    docker_socket, containerd_socket = hardened.agent_mode.checked_sockets
    docker_socket.chmod(0o666)
    make_socket(containerd_socket, 0o666)

    refused(
        f"use {docker_socket}, which is root over this sandbox",
        f"use {containerd_socket}, which is root over this sandbox",
    )


def test_a_writable_file_in_the_kit_is_refused(hardened, refused, read_only_kit) -> None:
    agents_md = read_only_kit / "AGENTS.md"
    agents_md.chmod(0o446)

    refused(f"change the agent kit: {agents_md} is writable")


def test_a_link_to_a_writable_folder_outside_the_kit_is_refused(hardened, refused, read_only_kit, tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o777)
    link = read_only_kit / "hooks" / "outside"
    with writable(link.parent):
        link.symlink_to(outside)

    refused(f"change the agent kit: {link} is writable")


def test_a_link_to_nothing_in_the_kit_is_refused(hardened, refused, read_only_kit, tmp_path) -> None:
    link = read_only_kit / "hooks" / "nowhere"
    with writable(link.parent):
        link.symlink_to(tmp_path / "nothing")

    refused(
        f"change the agent kit: {link} links to {tmp_path / 'nothing'}, which doesn't exist",
    )


def test_a_kit_folder_that_cant_be_listed_is_refused(hardened, refused, read_only_kit) -> None:
    """Listing is real, not modelled: the test user can't list a folder it has taken every permission from."""
    hooks = read_only_kit / "hooks"
    hooks.chmod(0o000)
    try:
        refused(
            startswith=f"change the agent kit unchecked: {hooks} can't be listed",
        )
    finally:
        hooks.chmod(0o555)


def test_a_folder_above_the_kit_the_agent_can_write_is_refused(hardened, refused, read_only_kit) -> None:
    """Renaming a folder above the mount and putting another kit at its path would change what the hooks' link,
    and every call into the runtime, reaches."""
    above = read_only_kit.parent
    above.chmod(0o757)
    try:
        refused(f"replace the agent kit: {above}, above it, is writable")
    finally:
        above.chmod(0o755)


def test_a_folder_above_the_kit_root_doesnt_own_is_refused(hardened, refused, read_only_kit) -> None:
    above = read_only_kit.parent.parent
    hardened.owners[above] = SOMEONE_ELSE.uid

    refused(
        f"replace the agent kit: {above}, above it, isn't owned by uid {ME.uid}",
    )


def test_a_sticky_folder_above_the_kit_counts_only_for_what_the_agent_owns(
    hardened, refused, read_only_kit, capsys
) -> None:
    """In a sticky folder anyone can write, as /tmp, only an entry's owner can rename it."""
    sticky, child = read_only_kit.parent.parent, read_only_kit.parent
    sticky.chmod(0o1777)
    try:
        assert harden.verify(read_only_kit, hardened.agent_mode) == []
        capsys.readouterr()
        hardened.owners[child] = AGENT_UID
        refused(
            f"replace the agent kit: {sticky}, above it, is writable",
        )
    finally:
        sticky.chmod(0o755)


def test_a_missing_kit_is_refused(hardened, tmp_path) -> None:
    """Without the kit's copy of the settings, the installed ones can't be compared: verify says so, rather
    than that they're older."""
    kit = tmp_path / "absent"
    kit_copy = kit / "claude" / "managed-settings.json"

    failures = harden.verify(kit, hardened.agent_mode)

    assert any("can't be listed" in failure for failure in failures), failures
    assert f"run with managed settings that can't be checked: {kit_copy} can't be read" in failures
    assert not any("older managed settings" in failure for failure in failures)


def test_a_missing_interpreter_is_refused(hardened, read_only_kit) -> None:
    python = Path(hardened.agent_mode.python)
    python.resolve().unlink()

    failures = harden.verify(read_only_kit, hardened.agent_mode)

    assert any(f.startswith("run without the hooks' interpreter:") and "is missing" in f for f in failures), failures


def test_an_interpreter_the_agent_can_write_is_refused(hardened, refused, read_only_kit) -> None:
    python = Path(hardened.agent_mode.python)
    python.resolve().chmod(0o757)

    refused(
        f"change the hooks' interpreter: {python} (resolving to {python.resolve()}) is writable",
    )


@pytest.mark.parametrize("sudo", ["missing", "failing", "unexecutable"])
def test_a_sudo_that_cant_reach_root_passes(hardened, read_only_kit, tmp_path, sudo: str) -> None:
    """Unexecutable is what root mode leaves, and what every later launch finds: it must count as no sudo."""
    agent_mode = hardened.agent_mode
    if sudo == "missing":
        agent_mode = dataclasses.replace(agent_mode, sudo=str(tmp_path / "absent"))
    elif sudo == "failing":
        stand_in(Path(agent_mode.sudo).parent, "sudo", 1)

    assert harden.verify(read_only_kit, agent_mode) == []


def test_a_missing_su_passes(hardened, read_only_kit, tmp_path) -> None:
    agent_mode = dataclasses.replace(hardened.agent_mode, su=str(tmp_path / "absent"))

    assert harden.verify(read_only_kit, agent_mode) == []


def test_verify_refuses_to_run_as_root(hardened, read_only_kit) -> None:
    """It checks what the agent can do; root can do anything."""
    with pytest.raises(harden.Refused, match="runs as the agent"):
        harden.verify(read_only_kit, hardened.root_mode)


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
    machine: TemporaryMachine, read_only_kit: Path, sudo_user: str
) -> None:
    """Removing sudo would lock a real machine's owner out: only sudo from the sandbox's agent may run it."""
    before = snapshot(machine)

    with pytest.raises(harden.Refused) as refused_by:
        harden.harden(read_only_kit, sudo_user, machine.root_mode)

    err = str(refused_by.value)
    assert "only runs inside a foundry sandbox" in err and f"(SUDO_USER is '{sudo_user or 'unset'}')" in err
    assert snapshot(machine) == before


def test_root_mode_refuses_without_root_changing_nothing(machine: TemporaryMachine, read_only_kit: Path) -> None:
    before = snapshot(machine)

    with pytest.raises(harden.Refused) as refused_by:
        harden.harden(read_only_kit, SUDO_USER, machine.agent_mode)

    err = str(refused_by.value)
    assert "only runs inside a foundry sandbox" in err and "(SUDO_USER is 'agent')" in err
    assert snapshot(machine) == before


def test_settings_from_an_older_kit_are_replaced(machine: TemporaryMachine, read_only_kit: Path) -> None:
    installed = machine.root_mode.managed_settings
    installed.parent.mkdir(parents=True)
    installed.write_text('{"permissions": {}}\n')
    installed.chmod(0o600)

    harden.harden(read_only_kit, SUDO_USER, machine.root_mode)

    assert installed.read_bytes() == (read_only_kit / "claude" / "managed-settings.json").read_bytes()
    assert stat.S_IMODE(installed.stat().st_mode) == 0o644


def test_a_settings_folder_anyone_could_write_is_closed(machine: TemporaryMachine, read_only_kit: Path) -> None:
    folder = machine.root_mode.managed_settings.parent
    folder.mkdir(parents=True)
    folder.chmod(0o777)

    harden.harden(read_only_kit, SUDO_USER, machine.root_mode)

    assert stat.S_IMODE(folder.stat().st_mode) == 0o755


def test_dockers_configuration_from_an_earlier_launch_is_kept(machine: TemporaryMachine, read_only_kit: Path) -> None:
    daemon_config = machine.root_mode.docker_daemon_config
    daemon_config.parent.mkdir(parents=True)
    daemon_config.write_text('{"group": "root"}\n')

    harden.harden(read_only_kit, SUDO_USER, machine.root_mode)

    assert daemon_config.read_text() == '{"group": "root"}\n'


def test_a_templates_own_docker_configuration_is_refused_changing_nothing(
    machine: TemporaryMachine, read_only_kit: Path
) -> None:
    """Checked before any step: removing sudo can't be undone, so root mode refuses while it still could run again."""
    daemon_config = machine.root_mode.docker_daemon_config
    daemon_config.parent.mkdir(parents=True)
    daemon_config.write_text('{"debug": true}\n')
    before = snapshot(machine)

    with pytest.raises(harden.Refused) as refused_by:
        harden.harden(read_only_kit, SUDO_USER, machine.root_mode)

    err = str(refused_by.value)
    assert "harden: refusing:" in err and "already has" in err
    assert snapshot(machine) == before


@pytest.mark.parametrize("command", ["sudo", "passwd"])
def test_a_command_root_mode_needs_that_cant_be_found_is_refused_changing_nothing(
    machine: TemporaryMachine, read_only_kit: Path, tmp_path: Path, command: str
) -> None:
    absent = str(tmp_path / "absent")
    if command == "sudo":
        root_mode = dataclasses.replace(machine.root_mode, sudo=absent)
    else:
        root_mode = dataclasses.replace(machine.root_mode, passwd=absent)
    before = snapshot(machine)

    with pytest.raises(harden.Refused) as refused_by:
        harden.harden(read_only_kit, SUDO_USER, root_mode)

    assert f"harden: refusing: can't find {tmp_path / 'absent'}" in str(refused_by.value)
    assert snapshot(machine) == before


def test_a_failing_step_leaves_sudo_for_the_next_launch(machine: TemporaryMachine, read_only_kit: Path) -> None:
    """Removing sudo comes last, being the one step that can't be undone: whatever fails before it, the next
    launch can run root mode again. No traceback."""
    failing_passwd = stand_in(machine.dir, "failing-passwd", 1)
    root_mode = dataclasses.replace(machine.root_mode, passwd=failing_passwd)

    with pytest.raises(harden.Refused) as refused_by:
        harden.harden(read_only_kit, SUDO_USER, root_mode)

    err = str(refused_by.value)
    assert "Traceback" not in err
    assert f"harden: refusing: `{failing_passwd} -l root` failed with exit code 1" in err
    assert "sudo is untouched, so the next launch runs this again" in err
    assert stat.S_IMODE(Path(root_mode.sudo).stat().st_mode) == 0o755


@pytest.mark.parametrize("damage", ["not UTF-8", "unreadable"])
def test_a_daemon_config_that_cant_be_read_is_refused_changing_nothing(
    machine: TemporaryMachine, read_only_kit: Path, damage: str
) -> None:
    daemon_config = machine.root_mode.docker_daemon_config
    daemon_config.parent.mkdir(parents=True)
    daemon_config.write_bytes(b"\xff\xfe")
    mode = stat.S_IMODE(daemon_config.stat().st_mode)
    before = snapshot(machine)
    if damage == "unreadable":
        daemon_config.chmod(0)

    try:
        with pytest.raises(harden.Refused) as refused_by:
            harden.harden(read_only_kit, SUDO_USER, machine.root_mode)
    finally:
        daemon_config.chmod(mode)

    err = str(refused_by.value)
    assert "Traceback" not in err and f"harden: refusing: can't read {daemon_config}" in err
    assert snapshot(machine) == before
