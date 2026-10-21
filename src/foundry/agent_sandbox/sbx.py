"""Docker Sandboxes (sbx), driven by a sandbox environment file."""

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.github_keys import GITHUB_HOST_KEYS
from foundry.agent_sandbox.host import HostPort
from foundry.agent_sandbox.ssh_agent import SshAddExitCode, SshAgent


class Sbx:
    """sbx commands for one sandbox, declared by the ``sbxenv.yaml`` in ``env_dir``.

    ``name`` must be the ``name:`` in that file; policy and secret commands
    address the sandbox by name, everything else through the file.

    Every call carries ``process_env``: sbx points a sandbox's forwarded agent
    at the SSH_AUTH_SOCK of each call aimed at it, so no call may carry
    another socket.
    """

    def __init__(self, host: HostPort, process_env: Mapping[str, str], name: str, env_dir: Path) -> None:
        self._host = host
        self._process_env = process_env
        self.name = name
        self.env_dir = env_dir

    @staticmethod
    def process_env(environ: Mapping[str, str], socket: Path) -> dict[str, str]:
        """The process environment every sbx call must carry: the sandbox's own agent socket."""
        env = {key: value for key, value in environ.items() if key != "SSH_AGENT_PID"}
        env["SSH_AUTH_SOCK"] = str(socket)
        return env

    def exists(self) -> bool:
        return self.exec_in("true").returncode == 0

    def create(self) -> None:
        """Create the sandbox from its environment file without attaching."""
        result = self._sbx("env", "create", "--auto-approve", str(self.env_dir))
        if result.returncode != 0:
            raise SandboxError(f"sbx env create failed: {result.stderr.strip()}")

    def remove(self) -> None:
        result = self._sbx("env", "rm", "--auto-approve", str(self.env_dir))
        if result.returncode != 0:
            raise SandboxError(f"sbx env rm failed: {result.stderr.strip()}")

    def exec_in(self, *cmd: str) -> subprocess.CompletedProcess[str]:
        """Run a command inside the sandbox, with the environment file's variables set."""
        return self._sbx("env", "exec", str(self.env_dir), "--", *cmd)

    def ensure_github_ssh_allowed(self) -> None:
        """sbx denies non-HTTP(S) TCP by default; git over SSH needs this route."""
        result = self._sbx("policy", "allow", "network", "--sandbox", self.name, "github.com:22")
        if result.returncode != 0:
            raise SandboxError(f"sbx policy allow failed: {result.stderr.strip()}")

    def ensure_known_hosts(self) -> None:
        """Trust GitHub's published host keys so the first SSH operation doesn't block."""
        setup = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/known_hosts && chmod 600 ~/.ssh/known_hosts"
        seed_one = "(grep -qxF '{key}' ~/.ssh/known_hosts || echo '{key}' >> ~/.ssh/known_hosts)"
        script = " && ".join((setup, *(seed_one.format(key=key) for key in GITHUB_HOST_KEYS)))
        result = self.exec_in("sh", "-c", script)
        if result.returncode != 0:
            raise SandboxError(f"seeding known_hosts failed: {result.stderr.strip()}")

    def set_github_token(self, token: str) -> None:
        result = self._sbx("secret", "set", "github", "--sandbox", self.name, "-t", token)
        if result.returncode != 0:
            raise SandboxError(f"sbx secret set failed: {result.stderr.strip()}")

    def clear_github_token(self) -> None:
        result = self._sbx("secret", "rm", "github", "--sandbox", self.name, "-f")
        if result.returncode != 0:
            raise SandboxError(f"sbx secret rm failed: {result.stderr.strip()}")

    def agent_fingerprints(self) -> set[str] | None:
        """Fingerprints of the keys the sandbox's agent offers, or None if no agent reaches it."""
        result = self.exec_in("ssh-add", "-l")
        if result.returncode == SshAddExitCode.HAS_KEYS:
            return {SshAgent.parse_fingerprint(line) for line in result.stdout.splitlines() if line.strip()}
        if result.returncode == SshAddExitCode.NO_KEYS:
            return set()
        if result.returncode == SshAddExitCode.NO_AGENT:
            return None
        raise SandboxError(f"could not list the sandbox's keys: {result.stderr.strip()}")

    def run_args(self, agent_args: Sequence[str]) -> tuple[str, ...]:
        """``sbx env run`` for the existing sandbox: attaches the agent."""
        args = ("sbx", "env", "run", "--auto-approve", str(self.env_dir))
        return (*args, "--", *agent_args) if agent_args else args

    def _sbx(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self._host.run(("sbx", *args), env=self._process_env)
