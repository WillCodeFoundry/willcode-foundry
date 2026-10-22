"""A dedicated ssh-agent per sandbox, reachable at a fixed socket path."""

import subprocess
from collections.abc import Sequence
from enum import IntEnum
from pathlib import Path

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import Host


def agent_socket_path(sandbox_name: str, uid: int) -> Path:
    """The sandbox's ssh-agent socket: /tmp/sbx-agents-<uid>/<sandbox_name>.sock.

    The directory is per user, since /tmp is shared; the launcher makes it
    private before starting the agent.
    """
    return Path(f"/tmp/sbx-agents-{uid}") / f"{sandbox_name}.sock"


class SshAddExitCode(IntEnum):
    """Exit codes from ``ssh-add -l``, wherever it's run - directly against this
    agent, or inside the sandbox against whatever agent is forwarded there.
    """

    HAS_KEYS = 0
    NO_KEYS = 1
    NO_AGENT = 2


class SshAgent:
    """An ssh-agent bound to ``socket_path``, reused across launches of one sandbox."""

    def __init__(self, host: Host, socket_path: Path) -> None:
        self._host = host
        self.socket_path = socket_path

    def ensure_running(self) -> None:
        """Start the agent unless one already answers on the socket.

        The caller must have already made ``socket_path``'s directory private to
        this user - a socket in a directory someone else controls could be
        their agent, not ours.
        """
        if self._is_running():
            return

        self._host.reset_socket(self.socket_path)  # stale socket from a dead agent
        # The env script ssh-agent prints is ignored on purpose: nothing in
        # this process should start using the sandbox's agent by accident.
        result = self._host.run(("ssh-agent", "-a", str(self.socket_path), "-s"))
        if result.returncode != 0 or not self._is_running():
            raise SandboxError(f"ssh-agent failed to start on {self.socket_path}")

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
        return {self.parse_fingerprint(line) for line in result.stdout.splitlines() if line.strip()}

    @staticmethod
    def parse_fingerprint(ssh_add_line: str) -> str:
        """The fingerprint from one ``ssh-add -l`` line: ``<bits> <fingerprint> <comment> (<type>)``."""
        return ssh_add_line.split()[1]

    def _is_running(self) -> bool:
        return self._ssh_add("-l").returncode in (SshAddExitCode.HAS_KEYS, SshAddExitCode.NO_KEYS)

    def _ssh_add(self, *args: str) -> subprocess.CompletedProcess[str]:
        # ssh-add only needs to find itself and reach the right agent - nothing else.
        environ = self._host.environ()
        env = {"SSH_AUTH_SOCK": str(self.socket_path)}
        if "PATH" in environ:
            env["PATH"] = environ["PATH"]
        return self._host.run(("ssh-add", *args), env=env)
