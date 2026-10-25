"""A dedicated ssh-agent per sandbox, reachable at a fixed socket path."""

import os
import re
import stat
import subprocess
import time
from collections.abc import Collection, Sequence
from enum import IntEnum
from pathlib import Path

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import Host

SSH_AGENT_SOCKETS_DIR = Path("/tmp/sbx-agents")  # session paths are too long for a socket; one user per machine

_RECENTLY_TOUCHED_SECONDS = 600  # covers a launch's sandbox creation and session-init


def parse_fingerprint(ssh_add_line: str) -> str:
    """The fingerprint from one ``ssh-add -l`` line: ``<bits> <fingerprint> <comment> (<type>)``."""
    return ssh_add_line.split()[1]


class SshAgentRegistry:
    """This user's ssh-agents, one per sandbox, each on a socket in one private directory.

    An agent is started with a fixed command line, so a later launch or prune can find it in the
    process list; one whose socket was touched in the last 10 minutes is never pruned, since its
    sandbox may not be live yet.
    """

    def __init__(self, host: Host, *, uid: int, sockets_dir: Path = SSH_AGENT_SOCKETS_DIR) -> None:
        self._host = host
        self._uid = uid
        self._sockets_dir = sockets_dir

    def ssh_agent(self, sandbox_name: str) -> "SshAgent":
        """This sandbox's ssh-agent; its ensure_running starts it, or reuses the one already there."""
        return SshAgent(self._host, self._socket_path(sandbox_name), self._uid)

    def prune(self, *, live_sandboxes: Collection[str]) -> list[str]:
        """Kill the ssh-agents of sandboxes not in ``live_sandboxes``, except recently touched ones.

        An agent whose socket is gone is killed too: nothing can reach it, but it still holds a
        key. Returns the names of the sandboxes whose agents were killed, sorted.
        """
        pruned = []
        for sandbox_name, pid in sorted(self._list_ssh_agents().items()):
            if sandbox_name in live_sandboxes or self._recently_touched(sandbox_name):
                continue
            try:
                self._host.kill_process(pid)
            except ProcessLookupError:
                continue  # it stopped meanwhile
            pruned.append(sandbox_name)
        return pruned

    def _socket_path(self, sandbox_name: str) -> Path:
        return self._sockets_dir / f"{sandbox_name}.sock"

    def _recently_touched(self, sandbox_name: str) -> bool:
        """Whether the sandbox's socket was touched in the last 10 minutes, as a launch in progress's is."""
        try:
            return time.time() - self._socket_path(sandbox_name).stat().st_mtime < _RECENTLY_TOUCHED_SECONDS
        except FileNotFoundError:
            return False  # no socket: not a launch in progress, since ensure_running creates it first

    def _list_ssh_agents(self) -> dict[str, int]:
        """This user's running ssh-agents, as sandbox name -> pid, whether or not their sockets still exist.

        A process is one of them if its command line is what _start_command gives for some sandbox's
        socket in the sockets directory. Two can share a sandbox name only if one is an orphan whose
        replacement started on the same socket; then one pid is kept here, and the next prune finds
        the other.
        """
        marker = "\0"  # stands in for the sandbox name; can't occur in a path or a command line
        before, after = " ".join(_start_command(self._socket_path(marker))).split(marker)
        started_by_registry = re.compile(re.escape(before) + r"([^/\s]+)" + re.escape(after))
        return {
            match[1]: pid
            for pid, command in self._host.list_processes(self._uid)
            if (match := started_by_registry.fullmatch(command))
        }


def _start_command(socket_path: Path) -> tuple[str, ...]:
    """How every ssh-agent is started; SshAgentRegistry._list_ssh_agents recognises them by this command line."""
    return ("ssh-agent", "-a", str(socket_path), "-s")


def _ensure_private_dir(private_dir: Path, uid: int) -> None:
    """Create private_dir as a directory only this user can use, refusing one we don't own.

    The sockets directory lives in /tmp, which is shared: another user could
    create it first, or put a symlink there pointing somewhere they control.
    """
    try:
        private_dir.mkdir(mode=0o700, exist_ok=True)
        info = os.lstat(private_dir)
        ours = stat.S_ISDIR(info.st_mode) and info.st_uid == uid
    except FileExistsError:  # a file, or a dangling symlink
        ours = False
    if not ours:
        raise SandboxError(f"{private_dir} is not a directory owned by you")
    private_dir.chmod(0o700)


class SshAddExitCode(IntEnum):
    """Exit codes from ``ssh-add -l``, wherever it's run - directly against this
    agent, or inside the sandbox against whatever agent is forwarded there.
    """

    HAS_KEYS = 0
    NO_KEYS = 1
    NO_AGENT = 2


class SshAgent:
    """An ssh-agent bound to ``socket_path``, reused across launches of one sandbox.

    Made by SshAgentRegistry.ssh_agent, which knows where each sandbox's socket is.
    """

    def __init__(self, host: Host, socket_path: Path, uid: int) -> None:
        self._host = host
        self.socket_path = socket_path
        self._uid = uid

    def ensure_running(self) -> None:
        """Start the agent unless one already answers on the socket, which lives in a directory private to us."""
        _ensure_private_dir(self.socket_path.parent, self._uid)
        if not self._is_running():
            self.socket_path.unlink(missing_ok=True)  # stale socket from a dead agent
            # Its env script is ignored, so this process never uses the sandbox's ssh-agent.
            result = self._host.run(_start_command(self.socket_path))
            if result.returncode != 0 or not self._is_running():
                raise SandboxError(f"ssh-agent failed to start on {self.socket_path}")
        self.socket_path.touch()  # SshAgentRegistry.prune spares it until the sandbox is live

    def replace_keys(self, key_paths: Sequence[Path]) -> None:
        """Make the keys at ``key_paths`` the only keys the agent holds.

        The agent belongs to one sandbox, so emptying it first is safe, and it
        stops keys from earlier launches (such as a rotated-out key) lingering.
        """
        result = self._ssh_add("-D")
        if result.returncode != 0:
            raise SandboxError(f"ssh-add could not empty the agent: {result.stderr.strip()}")
        for key_path in key_paths:
            result = self._ssh_add("-q", str(key_path))
            if result.returncode != 0:
                raise SandboxError(f"ssh-add failed for {key_path}: {result.stderr.strip()}")

    def list_key_fingerprints(self) -> set[str]:
        """Fingerprints of the keys the agent holds; empty if none, or if it doesn't answer."""
        result = self._ssh_add("-l")
        if result.returncode != SshAddExitCode.HAS_KEYS:
            return set()
        return {parse_fingerprint(line) for line in result.stdout.splitlines() if line.strip()}

    def _is_running(self) -> bool:
        return self._ssh_add("-l").returncode in (SshAddExitCode.HAS_KEYS, SshAddExitCode.NO_KEYS)

    def _ssh_add(self, *args: str) -> subprocess.CompletedProcess[str]:
        # ssh-add only needs to find itself and reach the right agent - nothing else.
        environ = self._host.environ()
        env = {"SSH_AUTH_SOCK": str(self.socket_path)}
        if "PATH" in environ:
            env["PATH"] = environ["PATH"]
        return self._host.run(("ssh-add", *args), env=env)
