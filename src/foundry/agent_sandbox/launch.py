"""Launch one sandbox from a sbxenv.yaml, with its own ssh-agent.

Imports nothing from the rest of foundry: it is given a directory holding
sbxenv.yaml, the agent kit mounted read-only in it, a private key, and what
to run before handing the terminal to the agent.
"""

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import Host, HostPort
from foundry.agent_sandbox.sbx import ENV_FILE_NAME, Sbx
from foundry.agent_sandbox.ssh_agent import SshAgent

SSH_AGENT_SOCKETS_DIR_PATH = Path("/tmp/sbx-agents")
"""Base directory for ssh-agent sockets; Host.ssh_agent_socket_path makes it private per-uid."""


@dataclass(frozen=True)
class Launch:
    """What to launch. Every path is absolute; the name and kit path match the env file."""

    sandbox_name: str
    env_dir_path: Path
    """Directory holding sbxenv.yaml; also where sbx env commands are pointed."""
    agent_kit_path: Path
    """The read-only mount declared in sbxenv.yaml; no private file may be inside it."""
    ssh_key_path: Path
    init_command: tuple[str, ...] = ()
    """Run inside the sandbox before the agent starts; the launch aborts if it fails."""
    github_token_path: Path | None = None
    """File holding a GitHub token for the sandbox; sbx reads it on the host when needed."""
    agent_args: tuple[str, ...] = ()


def ensure_paths_safe(agent_kit_path: Path, env_dir_path: Path, private_paths: Sequence[Path]) -> None:
    """Refuse layouts that would undo the sandbox's protections."""
    if ":" in str(agent_kit_path):
        raise SandboxError(f"agent kit path {str(agent_kit_path)!r} contains ':'")
    for private_path in private_paths:
        if private_path.is_relative_to(agent_kit_path):
            raise SandboxError(f"{str(private_path)!r} is inside the agent kit, readable by the sandbox")
    if env_dir_path.is_relative_to(agent_kit_path):
        raise SandboxError(
            f"environment file {str(env_dir_path)!r} is inside the agent kit; the sandbox could rewrite it"
        )


def ensure_forwarded_keys(ssh_agent: SshAgent, sbx: Sbx) -> None:
    """The sandbox must see exactly the keys we loaded, whatever sbx's settings claim."""
    expected = ssh_agent.list_key_fingerprints()
    seen = sbx.agent_fingerprints()
    if seen != expected:
        found = "no ssh-agent" if seen is None else f"keys {sorted(seen)}"
        raise SandboxError(
            f"the sandbox sees {found}, expected {sorted(expected)}.\n"
            "  check: sbx settings get ssh.agentForwardingEnabled  (must be true)\n"
            "         sbx settings get ssh.agentSocketPath         (must be empty)\n"
            "  then:  sbx daemon restart"
        )


def prepare_sandbox(launch: Launch, host: HostPort, ssh_agent: SshAgent, sbx: Sbx) -> None:
    """Everything up to, but not including, attaching the agent."""
    host.ensure_file_exists(launch.env_dir_path / ENV_FILE_NAME, "environment file")
    host.ensure_dir_exists(launch.agent_kit_path, "agent kit")
    host.ensure_file_exists(launch.ssh_key_path, "ssh key")
    private_paths = [launch.ssh_key_path]
    if launch.github_token_path is not None:
        host.ensure_file_exists(launch.github_token_path, "github token file")
        private_paths.append(launch.github_token_path)
    ensure_paths_safe(launch.agent_kit_path, launch.env_dir_path, private_paths)

    ssh_agent.ensure_running()
    ssh_agent.replace_keys([launch.ssh_key_path])

    if not sbx.start_if_exists():
        sbx.create()
    sbx.ensure_github_ssh_allowed()
    sbx.ensure_known_hosts()
    # Clear first: a token from an earlier launch must not outlive its file.
    sbx.clear_github_token()
    if launch.github_token_path is not None:
        sbx.set_github_token_source(launch.github_token_path)
    ensure_forwarded_keys(ssh_agent, sbx)

    if launch.init_command:
        result = sbx.exec_in_sandbox(*launch.init_command)
        if result.returncode != 0:
            raise SandboxError(
                f"init failed ({' '.join(launch.init_command)}):\n{result.stdout}{result.stderr}".rstrip()
            )


def describe_launch(launch: Launch, ssh_agent_socket_path: Path) -> str:
    notes = (
        f"ssh-agent: {ssh_agent_socket_path}",
        f"key:       {launch.ssh_key_path}",
        f"sandbox:   {launch.sandbox_name}",
        f"env file:  {launch.env_dir_path / ENV_FILE_NAME}",
        f"agent kit: {launch.agent_kit_path} (read-only)",
        f"github:    token from {launch.github_token_path}"
        if launch.github_token_path is not None
        else "github:    no token",
    )
    return "\n".join(f"==> {note}" for note in notes)


def run_sandbox(launch: Launch) -> NoReturn:
    """Prepare the sandbox and replace this process with ``sbx env run``.

    Raises SandboxError if anything before the hand-over fails.
    """
    host = Host(os.getuid())
    ssh_agent_socket_path = host.ssh_agent_socket_path(SSH_AGENT_SOCKETS_DIR_PATH, launch.sandbox_name)
    ssh_agent = SshAgent(host, ssh_agent_socket_path)
    process_env = Sbx.process_env(host.environ(), ssh_agent_socket_path)
    sbx = Sbx(host, process_env, launch.sandbox_name, launch.env_dir_path)
    host.ensure_private_dir(ssh_agent_socket_path.parent)
    prepare_sandbox(launch, host, ssh_agent, sbx)
    print(describe_launch(launch, ssh_agent_socket_path), file=sys.stderr)
    host.exec(sbx.run_command(launch.agent_args), process_env)
