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
from collections.abc import Iterable, Mapping
from pathlib import Path

from agent_runtime import contract

DOCKER_SOCKETS = (Path("/var/run/docker.sock"), Path("/var/run/docker/containerd/containerd.sock"))
MANAGED_SETTINGS = Path("/etc/claude-code/managed-settings.json")
DOCKER_DAEMON_CONFIG = Path("/etc/docker/daemon.json")
DOCKER_CONFIG = '{"group": "root"}'
SANDBOX_USER = "agent"
ROOT = (0, 0)


class HardenError(Exception):
    """A step can't go ahead; the message says why and what to change."""


def kit_settings(kit_dir: Path) -> Path:
    """The managed settings the kit holds, which the installed ones must be."""
    return kit_dir / "claude" / "managed-settings.json"


# --- Claude's managed settings -------------------------------------------------------


def harden_managed_settings(kit_copy: Path, installed: Path = MANAGED_SETTINGS, owner: tuple[int, int] = ROOT) -> None:
    """Install the kit's settings, owned by ``owner`` (root), so the agent can read them but not change or
    replace them. The directory is set too, in case it already existed. Written beside its final name and
    renamed over it, as install(1) does."""
    _install_dir(installed.parent, owner)
    _install_file(installed, kit_copy.read_bytes(), owner)


def check_managed_settings(installed: Path, kit_copy: Path, owner: int = 0) -> list[str]:
    """The installed settings exist, belong to the owner (root unless given), can't be written by the agent,
    and are the kit's. Settings from an older kit mean older permissions and hooks, so they count as not
    hardened."""
    if not installed.is_file():
        return [f"run without Claude's managed settings: {installed} is missing"]
    if installed.stat().st_uid != owner:
        return [f"replace Claude's managed settings: {installed} isn't owned by uid {owner}"]
    if os.access(installed, os.W_OK):
        return [f"change Claude's managed settings: {installed} is writable"]
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
    return succeeds([sudo, "-n", "true"])


def check_sudo(sudo: str = "sudo") -> list[str]:
    """The agent can't run sudo."""
    return ["run sudo"] if can_sudo(sudo) else []


def check_su(su: str = "su") -> list[str]:
    """The agent can't su to root. Root's password is locked, so su fails even without a terminal, and
    succeeds without one if root has none."""
    return ["su to root"] if succeeds([su, "root", "-c", "true"]) else []


# --- Docker --------------------------------------------------------------------------


def harden_docker(
    daemon_config: Path = DOCKER_DAEMON_CONFIG,
    sockets: Iterable[Path] = DOCKER_SOCKETS[:1],
    owner: tuple[int, int] = ROOT,
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
            os.chown(socket_path, -1, owner[1])


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


def check_python(python: str = contract.PYTHON, owner: int = 0) -> list[str]:
    """The interpreter every hook and the launch run resolves to a file root owns and the agent can't write."""
    resolved = Path(python).resolve()
    if not resolved.is_file():
        return [f"run hooks without their interpreter: {python} is missing"]
    if resolved.stat().st_uid != owner:
        return [f"replace the hooks' interpreter: {python} resolves to {resolved}, which isn't owned by uid {owner}"]
    if os.access(resolved, os.W_OK):
        return [f"change the hooks' interpreter: {python} resolves to {resolved}, which is writable"]
    return []


# --- the two modes -------------------------------------------------------------------


def harden(environ: Mapping[str, str] | None = None) -> int:
    """Root mode. Removing sudo would lock a real machine's owner out: only runs in a sandbox, via sudo from
    its agent user."""
    env = os.environ if environ is None else environ
    sudo_user = env.get("SUDO_USER", "")
    if os.geteuid() != 0 or sudo_user != SANDBOX_USER:
        print(
            f"harden: refusing: only runs inside a foundry sandbox, via sudo from its '{SANDBOX_USER}' user "
            f"(SUDO_USER is '{sudo_user or 'unset'}')",
            file=sys.stderr,
        )
        return 1
    kit_dir = contract.read_kit_dir(env)
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


def verify(environ: Mapping[str, str] | None = None) -> int:
    """Agent mode: run every check, as the agent, and refuse to start the agent if any fails."""
    if os.geteuid() == 0:
        print(
            "harden --verify: refusing: it runs as the agent, so it sees what the agent can do; root can do anything",
            file=sys.stderr,
        )
        return 1
    kit_dir = contract.read_kit_dir(environ)
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


def _install_dir(directory: Path, owner: tuple[int, int]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    os.chown(directory, *owner)
    directory.chmod(0o755)


def _install_file(target: Path, content: bytes, owner: tuple[int, int]) -> None:
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


def succeeds(command: list[str]) -> bool:
    """Whether ``command`` runs and exits 0, its output discarded. A command that is missing, or that can't
    execute, didn't succeed."""
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
    except OSError:  # FileNotFoundError, PermissionError, ...: as good as failing
        return False
    return result.returncode == 0
