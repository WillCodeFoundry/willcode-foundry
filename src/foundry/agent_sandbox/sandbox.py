"""The sandbox one launch prepares: the Sandbox port, and SbxCli, which drives it through sbx.

Sandbox is what the launcher needs, named for what each step does; SbxCli is the only
module that knows sbx's command lines.
"""

import json
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn, Protocol

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.github_host_keys import GITHUB_HOST_KEYS
from foundry.agent_sandbox.host import Host
from foundry.agent_sandbox.ssh_agent import SshAddExitCode, parse_fingerprint


class Sandbox(Protocol):
    """The sandbox one launch prepares, as the launcher needs it; SbxCli is the real one."""

    def start_if_exists(self) -> bool:
        """True if the sandbox exists; a stopped one is started."""
        ...

    def create(self) -> None:
        """Create the sandbox from its definition, without attaching."""
        ...

    def allow_github_ssh(self) -> None:
        """Let the sandbox reach github.com:22, for git over SSH."""
        ...

    def trust_github_host_keys(self) -> None:
        """Trust GitHub's published host keys inside, so the first SSH connection doesn't stop to ask."""
        ...

    def set_github_token_file(self, github_token_path: Path | None) -> None:
        """Give the sandbox the GitHub token in this file, read on the host; None takes any token away."""
        ...

    def forwarded_key_fingerprints(self) -> set[str] | None:
        """Fingerprints of the keys the sandbox's forwarded ssh-agent offers; None if none reaches it."""
        ...

    def run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """Run a command inside the sandbox, with its definition's variables, and wait for it."""
        ...

    def attach(self) -> NoReturn:
        """Replace this process with the agent's session in the sandbox."""
        ...


class SbxCli:
    """Sandbox through the sbx command line, for the sandbox whose definition is in ``definition_dir``.

    ``sandbox_name`` must be the ``name:`` in that file; policy and secret commands address the
    sandbox by name, everything else through the file. Every call carries the sandbox's own
    ssh-agent socket: sbx points a sandbox's forwarded agent at the SSH_AUTH_SOCK of each call
    aimed at it, so no call may carry another.
    """

    def __init__(self, host: Host, *, sandbox_name: str, definition_dir: Path, ssh_agent_socket_path: Path) -> None:
        self._host = host
        self._sandbox_name = sandbox_name
        self._definition_dir = definition_dir
        self._sbx_env = _sbx_env(host.environ(), ssh_agent_socket_path)

    def start_if_exists(self) -> bool:
        """True if the sandbox exists. A stopped sandbox is started, since reaching it starts it."""
        return self.run(("true",)).returncode == 0

    def create(self) -> None:
        result = self._sbx("env", "create", "--auto-approve", str(self._definition_dir))
        if result.returncode != 0:
            raise SandboxError(f"sbx env create failed: {result.stderr.strip()}")

    def allow_github_ssh(self) -> None:
        """sbx denies non-HTTP(S) TCP by default; git over SSH needs this route."""
        result = self._sbx("policy", "allow", "network", "--sandbox", self._sandbox_name, "github.com:22")
        if result.returncode != 0:
            raise SandboxError(f"sbx policy allow failed: {result.stderr.strip()}")

    def trust_github_host_keys(self) -> None:
        setup = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/known_hosts && chmod 600 ~/.ssh/known_hosts"
        seed_one = "(grep -qxF '{key}' ~/.ssh/known_hosts || echo '{key}' >> ~/.ssh/known_hosts)"
        script = " && ".join((setup, *(seed_one.format(key=key) for key in GITHUB_HOST_KEYS)))
        result = self.run(("sh", "-c", script))
        if result.returncode != 0:
            raise SandboxError(f"seeding known_hosts failed: {result.stderr.strip()}")

    def set_github_token_file(self, github_token_path: Path | None) -> None:
        """Clear the token first, so one from an earlier launch never outlives its file, then set it if given.

        Only the command that reads the file is stored, never the token, so it never appears in
        this process, its arguments or its errors.
        """
        result = self._sbx("secret", "rm", "github", "--sandbox", self._sandbox_name, "-f")
        if result.returncode != 0:
            raise SandboxError(f"sbx secret rm failed: {result.stderr.strip()}")
        if github_token_path is None:
            return
        read_token_command = f"cat {shlex.quote(str(github_token_path))}"
        result = self._sbx("secret", "set", "github", "--sandbox", self._sandbox_name, "--command", read_token_command)
        if result.returncode != 0:
            raise SandboxError(f"sbx secret set failed: {result.stderr.strip()}")

    def forwarded_key_fingerprints(self) -> set[str] | None:
        result = self.run(("ssh-add", "-l"))
        if result.returncode == SshAddExitCode.HAS_KEYS:
            return {parse_fingerprint(line) for line in result.stdout.splitlines() if line.strip()}
        if result.returncode == SshAddExitCode.NO_KEYS:
            return set()
        if result.returncode == SshAddExitCode.NO_AGENT:
            return None
        raise SandboxError(f"could not list the sandbox's keys: {result.stderr.strip()}")

    def run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return self._sbx("env", "exec", str(self._definition_dir), "--", *command)

    def attach(self) -> NoReturn:
        self._host.exec(("sbx", "env", "run", "--auto-approve", str(self._definition_dir)), self._sbx_env)

    def _sbx(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self._host.run(("sbx", *args), env=self._sbx_env)


def _sbx_env(environ: Mapping[str, str], ssh_agent_socket_path: Path) -> dict[str, str]:
    """The environment every sbx call aimed at a sandbox carries: that sandbox's own ssh-agent socket."""
    sbx_env = {key: value for key, value in environ.items() if key != "SSH_AGENT_PID"}
    sbx_env["SSH_AUTH_SOCK"] = str(ssh_agent_socket_path)
    return sbx_env


def list_live_sandboxes(host: Host) -> set[str]:
    """Names of the sandboxes ``sbx ls --json`` lists with any status but "stopped".

    Not aimed at one sandbox, so it runs in the host's own environment, with no sandbox's socket.
    """
    result = host.run(("sbx", "ls", "--json"), env=host.environ())
    if result.returncode != 0:
        raise SandboxError(f"sbx ls failed: {result.stderr.strip()}")
    return {sandbox["name"] for sandbox in json.loads(result.stdout)["sandboxes"] if sandbox["status"] != "stopped"}
