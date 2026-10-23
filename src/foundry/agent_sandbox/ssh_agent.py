"""A dedicated ssh-agent per sandbox, reachable at a fixed socket path."""

import os
import stat
import subprocess
import time
from collections.abc import Collection, Sequence
from enum import IntEnum
from pathlib import Path

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import Host


def agent_socket_path(sandbox_name: str, uid: int) -> Path:
    """The sandbox's ssh-agent socket: /tmp/sbx-agents-<uid>/<sandbox_name>.sock.

    The directory is per user, since /tmp is shared; SshAgent.ensure_running
    makes it private before using it. It stays in /tmp rather than the session
    directory because a socket's path is limited to about 100 bytes.
    """
    return _agent_sockets_dir(uid) / f"{sandbox_name}.sock"


def _agent_sockets_dir(uid: int) -> Path:
    return Path(f"/tmp/sbx-agents-{uid}")


def _start_command(socket_path: Path) -> tuple[str, ...]:
    """How every agent is started; list_ssh_agents relies on this command line."""
    return ("ssh-agent", "-a", str(socket_path), "-s")


RECENTLY_TOUCHED_SECONDS = 600  # covers a launch's sandbox creation and session-init


def _is_recently_touched(path: Path) -> bool:
    return time.time() - path.stat().st_mtime < RECENTLY_TOUCHED_SECONDS


def parse_fingerprint(ssh_add_line: str) -> str:
    """The fingerprint from one ``ssh-add -l`` line: ``<bits> <fingerprint> <comment> (<type>)``."""
    return ssh_add_line.split()[1]


def list_ssh_agents(host: Host, uid: int) -> dict[str, int]:
    """This launcher's running ssh-agents for ``uid``, as sandbox name -> pid, found by their command line."""
    head, tail = f"ssh-agent -a {_agent_sockets_dir(uid)}/", ".sock -s"
    return {
        command.removeprefix(head).removesuffix(tail): pid
        for pid, command in host.list_processes(uid)
        if command.startswith(head) and command.endswith(tail)
    }


def kill_ssh_agents(host: Host, uid: int, *, keep: Collection[str]) -> list[str]:
    """Kill this launcher's ssh-agents for ``uid``, except the kept sandboxes' and recently launched ones.

    Returns the killed agents' sandbox names. An agent without a socket is unreachable, so it is killed too.
    """
    agents = list_ssh_agents(host, uid)
    killed = []
    for name in sorted(agents):
        socket = agent_socket_path(name, uid)
        if name not in keep and not (socket.exists() and _is_recently_touched(socket)):
            host.kill_process(agents[name])
            killed.append(name)
    return killed


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
    """An ssh-agent bound to ``socket_path``, reused across launches of one sandbox."""

    def __init__(self, host: Host, socket_path: Path, uid: int) -> None:
        self._host = host
        self.socket_path = socket_path
        self._uid = uid

    def ensure_running(self) -> None:
        """Start the agent unless one already answers on the socket, which lives in a directory private to us."""
        _ensure_private_dir(self.socket_path.parent, self._uid)
        if not self._is_running():
            self.socket_path.unlink(missing_ok=True)  # stale socket from a dead agent
            # Its env script is ignored, so this process never uses the sandbox's agent.
            result = self._host.run(_start_command(self.socket_path))
            if result.returncode != 0 or not self._is_running():
                raise SandboxError(f"ssh-agent failed to start on {self.socket_path}")
        self.socket_path.touch()  # kill_ssh_agents spares it until the sandbox is live

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
