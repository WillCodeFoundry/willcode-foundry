"""Hardens a sandbox, and checks that it is hardened: the agent can't become root, can't change Claude's
managed settings, and can't change the code those settings and the launch run. Two modes, both run by
session-init:

    harden            as root, via sudo, on the first launch, while sudo still exists: installs the managed
                      settings, links the runtime their hooks run, and takes away sudo, su and Docker.
    harden --verify   as the agent, on every launch, before the agent starts: checks all of it.

Each step below sits beside the check that proves it. The checks run as the agent itself because sbx gives
agent processes the docker group by number, whatever /etc/group says: root, or a login through su, would see
different permissions than the agent has.

Both modes act on a Machine: where the sandbox's managed settings, Docker configuration, sockets,
interpreter and root-reaching commands are, who root is, the effective uid, what the agent can write, and
who owns what. SANDBOX is the real one, and the callers use it. The tests pass a temporary machine of their
own instead, so they run root mode and then agent mode on the same files, without root. Testing each step
and check alone would miss how they are called in sequence, which is where a launch breaks.

The interface is the two modes, harden and verify, and can_sudo, which session_init calls to decide whether
this launch can run root mode; every step and check is private. A check returns what the agent can still do,
one line each; an empty list means it passed.
"""

import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from agent_runtime import contract
from agent_runtime.agent_kit import AgentKit
from agent_runtime.files import atomic_symlink, atomic_write

_DOCKER_CONFIG = '{"group": "root"}'
SANDBOX_USER = "agent"


class Owner(NamedTuple):
    """Who a file belongs to. The steps set both; the checks compare the uid, what decides who can replace it."""

    uid: int
    gid: int


_ROOT = Owner(0, 0)


@dataclass(frozen=True, kw_only=True)
class Machine:
    """Where hardening acts and what it checks: the sandbox's system files, sockets and the commands that reach
    root, and what the agent can do to them. SANDBOX is the real one."""

    managed_settings: Path
    """Where Claude Code reads its managed settings."""
    hooks_runtime: Path
    """The path the managed hooks run the runtime from: a link root mode makes to the kit's. The hooks can't find
    it through AGENT_KIT_DIR, which a settings file the agent writes could change for Claude Code."""
    docker_daemon_config: Path
    """dockerd's configuration, where root mode gives its socket to root."""
    regrouped_socket: Path
    """The Docker socket root mode gives to root now, rather than when dockerd next starts."""
    checked_sockets: tuple[Path, ...]
    """The sockets agent mode checks the agent can't write: any of them is root over the sandbox."""
    python: str
    """The interpreter every hook and the launch run."""
    sudo: str
    su: str
    passwd: str
    root: Owner
    """Who the files root mode installs belong to."""
    euid: Callable[[], int]
    """The effective uid this process runs as: 0 in root mode, the agent's in agent mode."""
    can_write: Callable[[Path], bool]
    """Whether the agent can write ``path`` (for a link, its target)."""
    owner_of: Callable[[Path], int]
    """The uid that owns ``path``, which decides who can replace it."""


def _agent_can_write(path: Path) -> bool:
    return os.access(path, os.W_OK)


def _owner_of(path: Path) -> int:
    return path.stat().st_uid


SANDBOX = Machine(
    managed_settings=Path("/etc/claude-code/managed-settings.json"),
    hooks_runtime=Path("/etc/claude-code/agent_runtime.pyz"),
    docker_daemon_config=Path("/etc/docker/daemon.json"),
    regrouped_socket=Path("/var/run/docker.sock"),
    checked_sockets=(Path("/var/run/docker.sock"), Path("/var/run/docker/containerd/containerd.sock")),
    python=contract.PYTHON,
    sudo="sudo",
    su="su",
    passwd="passwd",
    root=_ROOT,
    euid=os.geteuid,
    can_write=_agent_can_write,
    owner_of=_owner_of,
)


class _Refused(Exception):
    """Root mode can't go ahead; the message says why and what to change. sudo is still there."""


# --- Claude's managed settings -------------------------------------------------------


def _harden_managed_settings(kit_copy: Path, installed: Path, owner: Owner) -> None:
    """Install the kit's settings, owned by ``owner`` (root), so the agent can read them but not change or
    replace them. The directory is set too, in case it already existed. Written beside its final name and
    renamed over it, as install(1) does."""
    _install_dir(installed.parent, owner)
    atomic_write(installed, kit_copy.read_bytes(), owner=owner)


def _check_managed_settings(installed: Path, kit_copy: Path, machine: Machine) -> list[str]:
    """The installed settings exist, belong to the machine's root, can't be written by the agent, sit in a folder
    that belongs to root and the agent can't write either, and are the kit's. Whoever can write the folder can
    swap the settings in it. Settings from an older kit mean older permissions and hooks, so they count as not
    hardened; without the kit's copy, they can't be checked."""
    if found := _check_owned_read_only(installed, "Claude's managed settings", str(installed), machine):
        return found
    if found := _check_root_folder(installed.parent, "Claude's managed settings", machine):
        return found
    kit_settings = _read_or_none(kit_copy)
    if kit_settings is None:
        return [f"run with managed settings that can't be checked: {kit_copy} can't be read"]
    if installed.read_bytes() != kit_settings:
        return [f"run with older managed settings: {installed} differs from {kit_copy}"]
    return []


# --- the runtime the managed hooks run ----------------------------------------------


def _harden_hooks_runtime(link: Path, kit_runtime: Path, owner: Owner) -> None:
    """Link the fixed path the managed hooks name to the kit's runtime, in a folder only root can write. A link,
    not a copy, so the runtime a later launch builds into the kit is the one the hooks run."""
    _install_dir(link.parent, owner)
    atomic_symlink(link, kit_runtime, owner=owner)


def _check_hooks_runtime(link: Path, kit_runtime: Path, machine: Machine) -> list[str]:
    """The fixed path is a link to the kit's runtime, which the kit's read-only mount keeps, in a folder root owns
    and the agent can't write."""
    if not link.is_symlink() and not link.exists():
        return [f"run Claude's hooks without their runtime: {link} is missing"]
    if not link.is_symlink() or link.resolve() != kit_runtime.resolve():
        return [f"run other code as Claude's hooks: {link} doesn't link to {kit_runtime}"]
    return _check_root_folder(link.parent, "the hooks' runtime", machine)


# --- sudo and su ---------------------------------------------------------------------


def _require_command(name: str, purpose: str) -> str:
    """Where ``name`` is. Hardening runs through sudo, so it is there to remove: not finding it is a refusal,
    not a step done."""
    found = shutil.which(name)
    if found is None:
        raise _Refused(f"can't find {name}, {purpose}; check the sandbox template's PATH")
    return found


def _lock_roots_password(passwd: str) -> None:
    """su needs root's password, and there is none."""
    locked = subprocess.run([passwd, "-l", "root"], stdout=subprocess.DEVNULL, check=False)
    if locked.returncode != 0:
        raise _Refused(f"`{passwd} -l root` failed with exit code {locked.returncode}{_SUDO_UNTOUCHED}")


def _remove_sudo(sudo: str) -> None:
    """sudo can't run, whatever its rules say. The one step that can't be undone, so it comes last."""
    Path(sudo).resolve().chmod(0)


def can_sudo(sudo: str) -> bool:
    """Whether ``sudo`` runs without a password. False, not an error, when it is missing or can't execute: on
    every launch after the first, hardening has left it mode 0."""
    return _succeeds([sudo, "-n", "true"])


def _check_sudo(sudo: str) -> list[str]:
    """The agent can't run sudo."""
    return ["run sudo"] if can_sudo(sudo) else []


def _check_su(su: str) -> list[str]:
    """The agent can't su to root. Root's password is locked, so su fails even without a terminal, and
    succeeds without one if root has none."""
    return ["su to root"] if _succeeds([su, "root", "-c", "true"]) else []


# --- Docker --------------------------------------------------------------------------


def _harden_docker(daemon_config: Path, socket_path: Path, owner: Owner) -> None:
    """Keep the agent off the Docker socket.

    ``docker run -v /:/host`` is root over this sandbox. sbx gives every process it starts the docker group
    by number, whatever /etc/group says, so leaving the group changes nothing: the socket has to leave the
    group instead. dockerd reads daemon.json each time it starts and recreates its socket owned by that group;
    the socket that exists now changes too.

    A template's own daemon.json is refused before any step.
    """
    _install_dir(daemon_config.parent, owner)
    atomic_write(daemon_config, f"{_DOCKER_CONFIG}\n".encode(), owner=owner)
    if _is_socket(socket_path):
        os.chown(socket_path, -1, owner.gid)


def _refuse_template_docker_config(daemon_config: Path) -> None:
    """Assumption: the sandbox template doesn't configure dockerd itself. If it ever does, stop with a clear
    message rather than merge into its settings. A daemon.json root mode wrote on an earlier launch is its own."""
    try:
        config = daemon_config.read_text() if daemon_config.exists() else None
    except (OSError, UnicodeDecodeError) as error:
        raise _Refused(f"can't read {daemon_config}: {error}") from None
    if config is not None and config.rstrip("\n") != _DOCKER_CONFIG:
        raise _Refused(
            f"this sandbox's template already has {daemon_config}.\n"
            "  foundry assumes the template leaves dockerd unconfigured, so that it can write\n"
            f"  {_DOCKER_CONFIG} there and keep the agent off the Docker socket. Merging into a\n"
            "  template's own Docker settings isn't supported; change agent_runtime.harden or the template."
        )


def _check_docker_sockets(sockets: Iterable[Path], can_write: Callable[[Path], bool]) -> list[str]:
    """The agent can't write to any of these sockets."""
    return [
        f"use {socket_path}, which is root over this sandbox"
        for socket_path in sockets
        if _is_socket(socket_path) and can_write(socket_path)
    ]


# --- what the hooks and the launch run -----------------------------------------------


def _check_kit_read_only(kit_dir: Path, can_write: Callable[[Path], bool]) -> list[str]:
    """The agent can't write anywhere in the agent kit, which holds the runtime every hook runs and the
    settings above are compared with. Proves the mount is read-only rather than assuming it.

    A link is judged by its target, wherever that is; a link to nothing fails, since creating its target
    would put a file in the kit. A folder that can't be listed fails too: what's in it can't be checked.
    """
    unreadable: list[OSError] = []
    for directory, subdirectories, files in os.walk(kit_dir, onerror=unreadable.append):
        for path in (Path(directory), *(Path(directory) / name for name in (*subdirectories, *files))):
            if path.is_symlink() and not path.exists():
                return [f"change the agent kit: {path} links to {os.readlink(path)}, which doesn't exist"]
            if can_write(path):
                return [f"change the agent kit: {path} is writable"]
    if unreadable:
        return [f"change the agent kit unchecked: {unreadable[0].filename} can't be listed ({unreadable[0].strerror})"]
    return []


def _check_folders_above_kit(kit_dir: Path, machine: Machine) -> list[str]:
    """Every folder from / down to the kit belongs to root, and the agent can't rename what's in it: the mount
    itself can't be renamed, but a folder above it could be, and another kit put at its path, which the hooks'
    link and every call into the runtime would then reach. In a sticky folder, as /tmp, only an entry's owner can
    rename it."""
    kit = kit_dir.resolve()
    if not kit.is_dir():
        return []  # the kit's own check reports it
    for folder, child in zip(reversed(kit.parents), [*reversed(kit.parents[:-1]), kit], strict=True):
        if machine.owner_of(folder) != machine.root.uid:
            return [f"replace the agent kit: {folder}, above it, isn't owned by uid {machine.root.uid}"]
        if machine.can_write(folder) and not (_is_sticky(folder) and machine.owner_of(child) != machine.euid()):
            return [f"replace the agent kit: {folder}, above it, is writable"]
    return []


def _check_python(python: str, machine: Machine) -> list[str]:
    """The interpreter every hook and the launch run resolves to a file root owns and the agent can't write."""
    resolved = Path(python).resolve()
    shown = f"{python} (resolving to {resolved})"
    return _check_owned_read_only(resolved, "the hooks' interpreter", shown, machine)


# --- the two modes -------------------------------------------------------------------


def harden(kit_dir: Path, sudo_user: str, machine: Machine = SANDBOX) -> int:
    """Root mode, given the kit to install settings from and the user sudo ran it for. Removing sudo would
    lock a real machine's owner out: only runs in a sandbox, via sudo from its agent user."""
    if machine.euid() != 0 or sudo_user != SANDBOX_USER:
        print(
            f"harden: refusing: only runs inside a foundry sandbox, via sudo from its '{SANDBOX_USER}' user "
            f"(SUDO_USER is '{sudo_user or 'unset'}')",
            file=sys.stderr,
        )
        return 1
    try:
        sudo, passwd = _preflight(machine)
        _run_steps(AgentKit(kit_dir), machine, sudo=sudo, passwd=passwd)
    except _Refused as error:
        print(f"harden: refusing: {error}", file=sys.stderr)
        return 1
    # Checked by `harden --verify`, which session-init runs next, as the agent.
    print(
        f"harden: managed settings installed, their hooks' runtime linked; sudo and su removed for {sudo_user}; "
        "Docker socket made root-only"
    )
    return 0


_SUDO_UNTOUCHED = "; sudo is untouched, so the next launch runs this again"


def _preflight(machine: Machine) -> tuple[str, str]:
    """Everything the steps need, checked before any of them: (sudo, passwd). Changes nothing."""
    _refuse_template_docker_config(machine.docker_daemon_config)
    return _require_command(machine.sudo, "to remove it"), _require_command(machine.passwd, "to lock root's password")


def _run_steps(agent_kit: AgentKit, machine: Machine, *, sudo: str, passwd: str) -> None:
    """Each step root mode takes, removing sudo last: a failure before it leaves root mode able to run again."""
    try:
        _harden_managed_settings(agent_kit.managed_settings, machine.managed_settings, machine.root)
        _harden_hooks_runtime(machine.hooks_runtime, agent_kit.runtime, machine.root)
        _harden_docker(machine.docker_daemon_config, machine.regrouped_socket, machine.root)
        _lock_roots_password(passwd)
        _remove_sudo(sudo)
    except OSError as error:
        raise _Refused(f"{error}{_SUDO_UNTOUCHED}") from None


def verify(kit_dir: Path, machine: Machine = SANDBOX) -> int:
    """Agent mode: run every check against the kit, as the agent, and refuse to start the agent if any fails."""
    if machine.euid() == 0:
        print(
            "harden --verify: refusing: it runs as the agent, so it sees what the agent can do; root can do anything",
            file=sys.stderr,
        )
        return 1
    found = [
        *_check_managed_settings(machine.managed_settings, AgentKit(kit_dir).managed_settings, machine),
        *_check_hooks_runtime(machine.hooks_runtime, AgentKit(kit_dir).runtime, machine),
        *_check_sudo(machine.sudo),
        *_check_su(machine.su),
        *_check_docker_sockets(machine.checked_sockets, machine.can_write),
        *_check_kit_read_only(kit_dir, machine.can_write),
        *_check_folders_above_kit(kit_dir, machine),
        *_check_python(machine.python, machine),
    ]
    if found:
        lines = "".join(f"  {line}\n" for line in found)
        sys.stderr.write(
            f"harden --verify: not starting the agent; it can still:\n{lines}"
            "A sandbox hardened by an older agent kit needs recreating:\n"
            "  sbx env rm --force sessions/<sandbox>, then delete sessions/<sandbox>/ and launch again.\n"
        )
        return 1
    print("harden --verify: hardened")
    return 0


# --- helpers -------------------------------------------------------------------------


def _check_owned_read_only(path: Path, what: str, shown: str, machine: Machine) -> list[str]:
    """``path`` exists, belongs to the machine's root and can't be written by the agent; ``shown`` names it in
    the failure, ``what`` says what it is."""
    if not path.is_file():
        return [f"run without {what}: {shown} is missing"]
    if machine.owner_of(path) != machine.root.uid:
        return [f"replace {what}: {shown} isn't owned by uid {machine.root.uid}"]
    if machine.can_write(path):
        return [f"change {what}: {shown} is writable"]
    return []


def _check_root_folder(folder: Path, what: str, machine: Machine) -> list[str]:
    """``folder`` belongs to the machine's root and the agent can't write it: whoever can could swap ``what``."""
    if machine.owner_of(folder) != machine.root.uid:
        return [f"replace {what}: {folder} isn't owned by uid {machine.root.uid}"]
    if machine.can_write(folder):
        return [f"replace {what}: {folder} is writable"]
    return []


def _install_dir(directory: Path, owner: Owner) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    os.chown(directory, *owner)
    directory.chmod(0o755)


def _read_or_none(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _is_sticky(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_ISVTX)


def _is_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.stat().st_mode)
    except OSError:
        return False


def _succeeds(command: list[str]) -> bool:
    """Whether ``command`` runs and exits 0, its output discarded. A command that is missing, or that can't
    execute, didn't succeed."""
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
    except OSError:  # FileNotFoundError, PermissionError, ...: as good as failing
        return False
    return result.returncode == 0
