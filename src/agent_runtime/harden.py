"""Hardens a sandbox, and checks that it is hardened: the agent can't become root, can't change Claude's
managed settings, and can't change the code those settings and the launch run. Two modes, both run by
session-init:

    harden            as root, via sudo, on the first launch, while sudo still exists: installs the managed
                      settings and takes away sudo, su and Docker.
    harden --verify   as the agent, on every launch, before the agent starts: checks all of it.

Each step below sits beside the check that proves it. The checks run as the agent itself because sbx gives
agent processes the docker group by number, whatever /etc/group says: root, or a login through su, would see
different permissions than the agent has.

A step takes the paths it changes, and a check what it inspects, as arguments, so the tests run them against
files, sockets and commands of their own. A check returns what the agent can still do, one line each; an
empty list means it passed.
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from agent_runtime import contract

DOCKER_SOCKETS = (Path("/var/run/docker.sock"), Path("/var/run/docker/containerd/containerd.sock"))
MANAGED_SETTINGS = Path("/etc/claude-code/managed-settings.json")
DOCKER_DAEMON_CONFIG = Path("/etc/docker/daemon.json")
DOCKER_CONFIG = '{"group": "root"}'
SANDBOX_USER = "agent"


class Owner(NamedTuple):
    """Who a file belongs to. The steps set both; the checks compare the uid, what decides who can replace it."""

    uid: int
    gid: int


ROOT = Owner(0, 0)


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
    su: str
    passwd: str
    root: Owner
    """Who the files root mode installs belong to."""
    euid: Callable[[], int]
    """The effective uid this process runs as: 0 in root mode, the agent's in agent mode."""
    can_write: Callable[[Path], bool]
    """Whether the agent can write ``path`` (for a link, its target)."""


def _agent_can_write(path: Path) -> bool:
    return os.access(path, os.W_OK)


SANDBOX = Machine(
    managed_settings=Path("/etc/claude-code/managed-settings.json"),
    docker_daemon_config=Path("/etc/docker/daemon.json"),
    regrouped_socket=Path("/var/run/docker.sock"),
    checked_sockets=(Path("/var/run/docker.sock"), Path("/var/run/docker/containerd/containerd.sock")),
    python=contract.PYTHON,
    sudo="sudo",
    su="su",
    passwd="passwd",
    root=ROOT,
    euid=os.geteuid,
    can_write=_agent_can_write,
)


class HardenError(Exception):
    """A step can't go ahead; the message says why and what to change."""


def kit_settings(kit_dir: Path) -> Path:
    """The managed settings the kit holds, which the installed ones must be."""
    return kit_dir / "claude" / "managed-settings.json"


# --- Claude's managed settings -------------------------------------------------------


def harden_managed_settings(kit_copy: Path, installed: Path = MANAGED_SETTINGS, owner: Owner = ROOT) -> None:
    """Install the kit's settings, owned by ``owner`` (root), so the agent can read them but not change or
    replace them. The directory is set too, in case it already existed. Written beside its final name and
    renamed over it, as install(1) does."""
    _install_dir(installed.parent, owner)
    _install_file(installed, kit_copy.read_bytes(), owner)


def check_managed_settings(installed: Path, kit_copy: Path, owner: Owner = ROOT) -> list[str]:
    """The installed settings exist, belong to the owner (root unless given), can't be written by the agent,
    and are the kit's. Settings from an older kit mean older permissions and hooks, so they count as not
    hardened."""
    if found := _check_owned_read_only(installed, "Claude's managed settings", str(installed), owner):
        return found
    if installed.read_bytes() != kit_copy.read_bytes():
        return [f"run with older managed settings: {installed} differs from {kit_copy}"]
    return []


# --- sudo and su ---------------------------------------------------------------------


def harden_sudo_and_su(sudo: str = "sudo") -> None:
    """sudo can't run, whatever its rules say; su needs root's password, and there is none.

    Refuses, changing nothing, if ``sudo`` can't be found: hardening runs through sudo, so it is there to
    remove, and reporting it removed when it wasn't found would be wrong.
    """
    found = shutil.which(sudo)
    if found is None:
        raise HardenError(f"can't find {sudo} to remove it; check the sandbox template's PATH and sudo")
    Path(found).resolve().chmod(0)
    subprocess.run(["passwd", "-l", "root"], stdout=subprocess.DEVNULL, check=True)


def can_sudo(sudo: str = "sudo") -> bool:
    """Whether sudo runs without a password. False, not an error, when it is missing or can't execute: on
    every launch after the first, hardening has left it mode 0."""
    return _succeeds([sudo, "-n", "true"])


def check_sudo(sudo: str = "sudo") -> list[str]:
    """The agent can't run sudo."""
    return ["run sudo"] if can_sudo(sudo) else []


def check_su(su: str = "su") -> list[str]:
    """The agent can't su to root. Root's password is locked, so su fails even without a terminal, and
    succeeds without one if root has none."""
    return ["su to root"] if _succeeds([su, "root", "-c", "true"]) else []


# --- Docker --------------------------------------------------------------------------


def harden_docker(
    daemon_config: Path = DOCKER_DAEMON_CONFIG,
    sockets: Iterable[Path] = DOCKER_SOCKETS[:1],
    owner: Owner = ROOT,
) -> None:
    """Keep the agent off the Docker socket.

    ``docker run -v /:/host`` is root over this sandbox. sbx gives every process it starts the docker group
    by number, whatever /etc/group says, so leaving the group changes nothing: the socket has to leave the
    group instead. dockerd reads daemon.json each time it starts and recreates its socket owned by that group;
    the socket that exists now changes too.

    Assumption: the sandbox template doesn't configure dockerd itself. If it ever does, stop with a clear
    message rather than merge into its settings.
    """
    if daemon_config.exists() and daemon_config.read_text().rstrip("\n") != DOCKER_CONFIG:
        raise HardenError(
            f"this sandbox's template already has {daemon_config}.\n"
            "  foundry assumes the template leaves dockerd unconfigured, so that it can write\n"
            f"  {DOCKER_CONFIG} there and keep the agent off the Docker socket. Merging into a\n"
            "  template's own Docker settings isn't supported; change agent_runtime.harden or the template."
        )
    _install_dir(daemon_config.parent, owner)
    _install_file(daemon_config, f"{DOCKER_CONFIG}\n".encode(), owner)
    for socket_path in sockets:
        if _is_socket(socket_path):
            os.chown(socket_path, -1, owner.gid)


def check_docker_sockets(sockets: Iterable[Path]) -> list[str]:
    """The agent can't write to any of these sockets."""
    return [
        f"use {socket_path}, which is root over this sandbox"
        for socket_path in sockets
        if _is_socket(socket_path) and os.access(socket_path, os.W_OK)
    ]


# --- what the hooks and the launch run -----------------------------------------------


def check_kit_read_only(kit_dir: Path) -> list[str]:
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
            if os.access(path, os.W_OK):
                return [f"change the agent kit: {path} is writable"]
    if unreadable:
        return [f"change the agent kit unchecked: {unreadable[0].filename} can't be listed ({unreadable[0].strerror})"]
    return []


def check_python(python: str = contract.PYTHON, owner: Owner = ROOT) -> list[str]:
    """The interpreter every hook and the launch run resolves to a file root owns and the agent can't write."""
    resolved = Path(python).resolve()
    return _check_owned_read_only(resolved, "the hooks' interpreter", f"{python} (resolving to {resolved})", owner)


# --- the two modes -------------------------------------------------------------------


def harden(kit_dir: Path, sudo_user: str) -> int:
    """Root mode, given the kit to install settings from and the user sudo ran it for. Removing sudo would
    lock a real machine's owner out: only runs in a sandbox, via sudo from its agent user."""
    if os.geteuid() != 0 or sudo_user != SANDBOX_USER:
        print(
            f"harden: refusing: only runs inside a foundry sandbox, via sudo from its '{SANDBOX_USER}' user "
            f"(SUDO_USER is '{sudo_user or 'unset'}')",
            file=sys.stderr,
        )
        return 1
    try:
        harden_managed_settings(kit_settings(kit_dir))
        harden_sudo_and_su()
        harden_docker()
    except HardenError as error:
        print(f"harden: refusing: {error}", file=sys.stderr)
        return 1
    # Checked by `harden --verify`, which session-init runs next, as the agent.
    print(f"harden: managed settings installed; sudo and su removed for {sudo_user}; Docker socket made root-only")
    return 0


def verify(kit_dir: Path) -> int:
    """Agent mode: run every check against the kit, as the agent, and refuse to start the agent if any fails."""
    if os.geteuid() == 0:
        print(
            "harden --verify: refusing: it runs as the agent, so it sees what the agent can do; root can do anything",
            file=sys.stderr,
        )
        return 1
    found = [
        *check_managed_settings(MANAGED_SETTINGS, kit_settings(kit_dir)),
        *check_sudo(),
        *check_su(),
        *check_docker_sockets(DOCKER_SOCKETS),
        *check_kit_read_only(kit_dir),
        *check_python(),
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


def _check_owned_read_only(path: Path, what: str, shown: str, owner: Owner) -> list[str]:
    """``path`` exists, belongs to ``owner`` and can't be written by the agent; ``shown`` names it in the
    failure, ``what`` says what it is."""
    if not path.is_file():
        return [f"run without {what}: {shown} is missing"]
    if path.stat().st_uid != owner.uid:
        return [f"replace {what}: {shown} isn't owned by uid {owner.uid}"]
    if os.access(path, os.W_OK):
        return [f"change {what}: {shown} is writable"]
    return []


def _install_dir(directory: Path, owner: Owner) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    os.chown(directory, *owner)
    directory.chmod(0o755)


def _install_file(target: Path, content: bytes, owner: Owner) -> None:
    descriptor, partial_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    partial = Path(partial_name)
    try:
        with os.fdopen(descriptor, "wb") as partial_file:
            partial_file.write(content)
        os.chown(partial, *owner)
        partial.chmod(0o644)
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)


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
