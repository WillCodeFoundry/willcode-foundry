"""Hardens a sandbox, and checks that it is hardened: the agent can't become root, can't change Claude's
managed settings, and can't change the code those settings and the launch run. Two modes:

    harden   as root, via sudo, on the first launch, while sudo still exists: installs the managed settings,
             links the runtime their hooks run, and takes away Docker, su and, last, sudo.
    verify   as the agent, on every launch, before the agent starts: checks all of it.

Each step sits beside the check that proves it. The checks run as the agent because sbx gives agent processes
the docker group by number, whatever /etc/group says: root would see other permissions than the agent has.

Both modes act on a Machine, so the tests run root mode and then agent mode on the same temporary files,
without root. A check returns what the agent can still do, one line each, read after "it can still:".
"""

import json
import os
import shlex
import shutil
import stat
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from agent_runtime import contract
from agent_runtime.agent_kit import PYTHON, RUNTIME_PYZ, AgentKit
from agent_runtime.files import atomic_symlink, atomic_write

_DOCKER_CONFIG = '{"group": "root"}'
SANDBOX_USER = contract.SANDBOX_USER


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
    docker_daemon_config: Path
    """dockerd's configuration, where root mode gives its socket to root."""
    regrouped_socket: Path
    """The Docker socket root mode gives to root now, rather than when dockerd next starts."""
    checked_sockets: tuple[Path, ...]
    """The sockets agent mode checks the agent can't write: any of them is root over the sandbox."""
    python: str
    """The interpreter every hook and the launch run."""
    sudo: str
    """The command that runs root mode, and that root mode removes."""
    su: str
    """The command that would reach root with root's password, which root mode locks."""
    passwd: str
    """The command that locks root's password."""
    root_owner: Owner
    """Who the files root mode installs belong to."""
    euid: Callable[[], int]
    """The effective uid this process runs as: 0 in root mode, the agent's in agent mode."""
    can_write: Callable[[Path], bool]
    """Whether the agent can write ``path`` (for a link, its target)."""
    owner_of: Callable[[Path], int]
    """The uid that owns ``path``, which decides who can replace it."""

    @property
    def hooks_runtime_link(self) -> Path:
        """The path the managed hooks run the runtime from, beside the settings: a link root mode makes to the
        kit's. Not AGENT_KIT_DIR, which a settings file the agent writes could change for Claude Code."""
        return self.managed_settings.parent / RUNTIME_PYZ.name


def _agent_can_write(path: Path) -> bool:
    return os.access(path, os.W_OK)


def _owner_of(path: Path) -> int:
    return path.stat().st_uid


SANDBOX = Machine(
    managed_settings=Path("/etc/claude-code/managed-settings.json"),
    docker_daemon_config=Path("/etc/docker/daemon.json"),
    regrouped_socket=Path("/var/run/docker.sock"),
    checked_sockets=(Path("/var/run/docker.sock"), Path("/var/run/docker/containerd/containerd.sock")),
    python=PYTHON,
    sudo="sudo",
    su="su",
    passwd="passwd",
    root_owner=_ROOT,
    euid=os.geteuid,
    can_write=_agent_can_write,
    owner_of=_owner_of,
)


class Refused(Exception):
    """A mode can't go ahead; the message, the whole of it, says why and what to change. In root mode, sudo is
    still there."""


# --- Claude's managed settings -------------------------------------------------------


def _harden_managed_settings(agent_kit: AgentKit, machine: Machine) -> None:
    """Install the kit's settings, root's and read-only, in a folder only root can write."""
    _install_dir(machine.managed_settings.parent, machine.root_owner)
    atomic_write(machine.managed_settings, agent_kit.managed_settings.read_bytes(), owner=machine.root_owner)


def _check_managed_settings(agent_kit: AgentKit, machine: Machine) -> list[str]:
    """Settings and their folder must be root-owned and unwritable, and match the kit: whoever can write the
    folder can swap the file, and an older kit's settings mean older hooks. Each hook must run the runtime
    through the link, which proves the settings and the link agree on this machine."""
    installed = machine.managed_settings
    if failures := _check_owned_read_only(installed, machine, label="Claude's managed settings"):
        return failures
    if failures := _check_root_folder(installed.parent, machine, label="Claude's managed settings"):
        return failures
    kit_settings = _read_or_none(agent_kit.managed_settings)
    if kit_settings is None:
        return [f"run with managed settings that can't be checked: {agent_kit.managed_settings} can't be read"]
    if installed.read_bytes() != kit_settings:
        return [f"run with older managed settings: {installed} differs from {agent_kit.managed_settings}"]
    link = str(machine.hooks_runtime_link)
    return [
        f"run a hook that skips the runtime's link, {link}: {command}"
        for command in _hook_commands(kit_settings)
        if link not in shlex.split(command)
    ]


def _hook_commands(settings: bytes) -> list[str]:
    """Every hook command in Claude Code's settings: hooks.<event>[].hooks[].command."""
    try:
        hooks = json.loads(settings).get("hooks", {})
    except (json.JSONDecodeError, AttributeError):
        return ["(the settings aren't a JSON object)"]
    return [
        hook.get("command", "") for entries in hooks.values() for entry in entries for hook in entry.get("hooks", [])
    ]


# --- the runtime the managed hooks run ----------------------------------------------


def _harden_hooks_runtime(agent_kit: AgentKit, machine: Machine) -> None:
    """Link the path the managed hooks name to the kit's runtime, in a folder only root can write. A link, not a
    copy, so the runtime a later launch builds into the kit is the one the hooks run."""
    link = machine.hooks_runtime_link
    _install_dir(link.parent, machine.root_owner)
    atomic_symlink(link, agent_kit.runtime, owner=machine.root_owner)


def _check_hooks_runtime(agent_kit: AgentKit, machine: Machine) -> list[str]:
    """The link leads to the kit's runtime, which the read-only mount keeps, from a folder root owns and the agent
    can't write."""
    link = machine.hooks_runtime_link
    if not (link.is_symlink() or link.exists()):
        return [f"run Claude's hooks without their runtime: {link} is missing"]
    if not link.is_symlink() or link.resolve() != agent_kit.runtime.resolve():
        return [f"run other code as Claude's hooks: {link} doesn't link to {agent_kit.runtime}"]
    return _check_root_folder(link.parent, machine, label="the hooks' runtime")


# --- sudo and su ---------------------------------------------------------------------


def _require_command(name: str, purpose: str) -> str:
    """Where ``name`` is. Hardening runs through sudo, so it is there to remove: not finding it is a refusal,
    not a step done."""
    found = shutil.which(name)
    if found is None:
        raise Refused(f"can't find {name}, {purpose}; check the sandbox template's PATH")
    return found


def _lock_roots_password(passwd: str) -> None:
    """su needs root's password, and there is none."""
    locked = subprocess.run([passwd, "-l", "root"], stdout=subprocess.DEVNULL, check=False)
    if locked.returncode != 0:
        raise Refused(f"`{passwd} -l root` failed with exit code {locked.returncode}{_SUDO_UNTOUCHED}")


def _remove_sudo(sudo: str) -> None:
    """sudo can't run, whatever its rules say. The one step that can't be undone, so it comes last."""
    Path(sudo).resolve().chmod(0)


def can_sudo(sudo: str) -> bool:
    """Whether ``sudo`` runs without a password. False, not an error, when it is missing or can't execute: on
    every launch after the first, hardening has left it mode 0."""
    return _succeeds([sudo, "-n", "true"])


def _check_sudo(machine: Machine) -> list[str]:
    return ["run sudo"] if can_sudo(machine.sudo) else []


def _check_su(machine: Machine) -> list[str]:
    """Root's password is locked, so su fails even without a terminal, and succeeds without one if root has
    none."""
    return ["su to root"] if _succeeds([machine.su, "root", "-c", "true"]) else []


# --- Docker --------------------------------------------------------------------------


def _harden_docker(machine: Machine) -> None:
    """Keep the agent off the Docker socket.

    ``docker run -v /:/host`` is root over this sandbox. sbx gives every process it starts the docker group
    by number, whatever /etc/group says, so leaving the group changes nothing: the socket has to leave the
    group instead. dockerd reads daemon.json each time it starts and recreates its socket owned by that group;
    the socket that exists now changes too.

    A template's own daemon.json is refused before any step.
    """
    _install_dir(machine.docker_daemon_config.parent, machine.root_owner)
    atomic_write(machine.docker_daemon_config, f"{_DOCKER_CONFIG}\n".encode(), owner=machine.root_owner)
    if _is_socket(machine.regrouped_socket):
        os.chown(machine.regrouped_socket, -1, machine.root_owner.gid)


def _refuse_template_docker_config(daemon_config: Path) -> None:
    """Assumption: the sandbox template doesn't configure dockerd itself. If it ever does, stop with a clear
    message rather than merge into its settings. A daemon.json root mode wrote on an earlier launch is its own."""
    try:
        config = daemon_config.read_text() if daemon_config.exists() else None
    except (OSError, UnicodeDecodeError) as error:
        raise Refused(f"can't read {daemon_config}: {error}") from None
    if config is not None and config.rstrip("\n") != _DOCKER_CONFIG:
        raise Refused(
            f"this sandbox's template already has {daemon_config}.\n"
            "  foundry assumes the template leaves dockerd unconfigured, so that it can write\n"
            f"  {_DOCKER_CONFIG} there and keep the agent off the Docker socket. Merging into a\n"
            "  template's own Docker settings isn't supported; change agent_runtime.harden or the template."
        )


def _check_docker_sockets(machine: Machine) -> list[str]:
    return [
        f"use {socket_path}, which is root over this sandbox"
        for socket_path in machine.checked_sockets
        if _is_socket(socket_path) and machine.can_write(socket_path)
    ]


# --- what the hooks and the launch run -----------------------------------------------


def _check_kit_read_only(agent_kit: AgentKit, machine: Machine) -> list[str]:
    """Nothing in the kit is writable by the agent: proves the mount is read-only rather than assuming it. A link
    is judged by its target; a link to nothing fails, since creating its target would put a file in the kit; a
    folder that can't be listed fails, since what's in it can't be checked."""
    unreadable: list[OSError] = []
    for path in _walk(agent_kit.dir, unreadable):
        if path.is_symlink() and not path.exists():
            return [f"change the agent kit: {path} links to {os.readlink(path)}, which doesn't exist"]
        if machine.can_write(path):
            return [f"change the agent kit: {path} is writable"]
    if unreadable:
        return [f"change the agent kit unchecked: {unreadable[0].filename} can't be listed ({unreadable[0].strerror})"]
    return []


def _check_folders_above_kit(agent_kit: AgentKit, machine: Machine) -> list[str]:
    """Every folder from / down to the kit is root's, and lets the agent rename nothing on the way: the mount
    can't be renamed, but a folder above it could be, and another kit put at the path the hooks' link and every
    call into the runtime reach. In a sticky folder, as /tmp, only an entry's owner can rename it."""
    kit = agent_kit.dir.resolve()
    if not kit.is_dir():
        return []  # the kit's own check reports it
    for folder, child in zip(reversed(kit.parents), [*reversed(kit.parents[:-1]), kit], strict=True):
        if machine.owner_of(folder) != machine.root_owner.uid:
            return [f"replace the agent kit: {folder}, above it, isn't owned by uid {machine.root_owner.uid}"]
        if machine.can_write(folder) and not (_is_sticky(folder) and machine.owner_of(child) != machine.euid()):
            return [f"replace the agent kit: {folder}, above it, is writable"]
    return []


def _check_python(machine: Machine) -> list[str]:
    """The interpreter every hook and the launch run resolves to a file root owns and the agent can't write."""
    resolved = Path(machine.python).resolve()
    return _check_owned_read_only(
        resolved, machine, label="the hooks' interpreter", display=f"{machine.python} (resolving to {resolved})"
    )


# --- the two modes -------------------------------------------------------------------


def harden(agent_kit_dir: Path, sudo_user: str, machine: Machine = SANDBOX) -> None:
    """Root mode, given the kit to install settings from and the user sudo ran it for. Raises Refused, whose
    message says why, when it can't go ahead. Removing sudo would lock a real machine's owner out: only runs in
    a sandbox, via sudo from its agent user."""
    if machine.euid() != 0 or sudo_user != SANDBOX_USER:
        raise Refused(
            f"harden: refusing: only runs inside a foundry sandbox, via sudo from its '{SANDBOX_USER}' user "
            f"(SUDO_USER is '{sudo_user or 'unset'}')"
        )
    try:
        sudo, passwd = _preflight(machine)
        _run_steps(AgentKit(agent_kit_dir), machine, sudo=sudo, passwd=passwd)
    except Refused as error:
        raise Refused(f"harden: refusing: {error}") from None


_SUDO_UNTOUCHED = "; sudo is untouched, so the next launch runs this again"


def _preflight(machine: Machine) -> tuple[str, str]:
    """Everything the steps need, checked before any of them: (sudo, passwd). Changes nothing."""
    _refuse_template_docker_config(machine.docker_daemon_config)
    return _require_command(machine.sudo, "to remove it"), _require_command(machine.passwd, "to lock root's password")


def _run_steps(agent_kit: AgentKit, machine: Machine, *, sudo: str, passwd: str) -> None:
    """Each step root mode takes, removing sudo last: a failure before it leaves root mode able to run again."""
    try:
        _harden_managed_settings(agent_kit, machine)
        _harden_hooks_runtime(agent_kit, machine)
        _harden_docker(machine)
        _lock_roots_password(passwd)
        _remove_sudo(sudo)
    except OSError as error:
        raise Refused(f"{error}{_SUDO_UNTOUCHED}") from None


def verify(agent_kit_dir: Path, machine: Machine = SANDBOX) -> list[str]:
    """Agent mode: what the agent can still do, one line each, after every check against the kit; empty when
    hardened. Raises Refused as root, who can do anything."""
    if machine.euid() == 0:
        raise Refused("verify: refusing: it runs as the agent, so it sees what the agent can do; root can do anything")
    agent_kit = AgentKit(agent_kit_dir)
    return [
        *_check_managed_settings(agent_kit, machine),
        *_check_hooks_runtime(agent_kit, machine),
        *_check_sudo(machine),
        *_check_su(machine),
        *_check_docker_sockets(machine),
        *_check_kit_read_only(agent_kit, machine),
        *_check_folders_above_kit(agent_kit, machine),
        *_check_python(machine),
    ]


# --- helpers -------------------------------------------------------------------------


def _check_owned_read_only(path: Path, machine: Machine, *, label: str, display: str | None = None) -> list[str]:
    """``path`` exists, is root's and the agent can't write it. ``label`` says what it is; ``display`` names it,
    the path by default."""
    shown = display or str(path)
    if not path.is_file():
        return [f"run without {label}: {shown} is missing"]
    if machine.owner_of(path) != machine.root_owner.uid:
        return [f"replace {label}: {shown} isn't owned by uid {machine.root_owner.uid}"]
    if machine.can_write(path):
        return [f"change {label}: {shown} is writable"]
    return []


def _check_root_folder(folder: Path, machine: Machine, *, label: str) -> list[str]:
    """``folder`` is root's and the agent can't write it: whoever can could swap what ``label`` names."""
    if machine.owner_of(folder) != machine.root_owner.uid:
        return [f"replace {label}: {folder} isn't owned by uid {machine.root_owner.uid}"]
    if machine.can_write(folder):
        return [f"replace {label}: {folder} is writable"]
    return []


def _install_dir(directory: Path, owner: Owner) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    os.chown(directory, *owner)
    directory.chmod(0o755)  # everyone may read and enter it; only root may change it


def _read_or_none(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _walk(top: Path, unreadable: list[OSError]) -> Iterator[Path]:
    """``top`` and everything under it, folders and links included; folders that can't be listed go to
    ``unreadable``."""
    for directory, subdirectories, files in os.walk(top, onerror=unreadable.append):
        yield Path(directory)
        for name in (*subdirectories, *files):
            yield Path(directory) / name


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
