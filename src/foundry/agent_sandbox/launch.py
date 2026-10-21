"""Launch one sandbox from a sbxenv.yaml, with its own ssh-agent.

Knows nothing about roles, tasks or the foundry layout: it is given a
directory holding sbxenv.yaml, a private key, and what to run before
handing the terminal to the agent.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import Host, HostPort
from foundry.agent_sandbox.sbx import Sbx
from foundry.agent_sandbox.ssh_agent import SshAgent

SOCKETS_DIR = Path("/tmp/sbx-agents")
"""Base directory for ssh-agent sockets; Host.socket_path makes it private per-uid."""


@dataclass(frozen=True)
class Launch:
    """What to launch. Every path is absolute; name and context match the env file."""

    name: str
    env_dir: Path
    """Directory holding sbxenv.yaml; also where sbx env commands are pointed."""
    context: Path
    """The read-only mount declared in sbxenv.yaml, checked against ssh_key."""
    ssh_key: Path
    init: tuple[str, ...] = ()
    """Command run inside the sandbox before the agent starts; abort if it fails."""
    github_token: str | None = None
    agent_args: tuple[str, ...] = ()
    fresh: bool = False
    """Remove an existing sandbox of this name first."""


def ensure_paths_safe(context: Path, ssh_key: Path, env_dir: Path) -> None:
    """Refuse layouts that would undo the sandbox's protections."""
    if ":" in str(context):
        raise SandboxError(f"context path {str(context)!r} contains ':'")
    if ssh_key.is_relative_to(context):
        raise SandboxError(f"ssh key {str(ssh_key)!r} is inside the context, readable by the sandbox")
    if env_dir.is_relative_to(context):
        raise SandboxError(f"environment file {str(env_dir)!r} is inside the context; the sandbox could rewrite it")


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


def prepare(launch: Launch, host: HostPort, ssh_agent: SshAgent, sbx: Sbx) -> None:
    """Everything up to, but not including, attaching the agent."""
    host.ensure_file_exists(launch.env_dir / "sbxenv.yaml", "environment file")
    host.ensure_dir_exists(launch.context, "context")
    host.ensure_file_exists(launch.ssh_key, "ssh key")
    ensure_paths_safe(launch.context, launch.ssh_key, launch.env_dir)

    ssh_agent.ensure_running()
    ssh_agent.replace_keys([launch.ssh_key])

    if launch.fresh and sbx.exists():
        sbx.remove()
    if not sbx.exists():
        sbx.create()
    sbx.ensure_github_ssh_allowed()
    sbx.ensure_known_hosts()
    if launch.github_token is not None:
        sbx.set_github_token(launch.github_token)
    else:
        sbx.clear_github_token()
    ensure_forwarded_keys(ssh_agent, sbx)

    if launch.init:
        result = sbx.exec_in(*launch.init)
        if result.returncode != 0:
            raise SandboxError(f"init failed ({' '.join(launch.init)}):\n{result.stdout}{result.stderr}".rstrip())


def description(launch: Launch, socket: Path) -> str:
    notes = (
        f"ssh-agent: {socket}",
        f"key:       {launch.ssh_key}",
        f"sandbox:   {launch.name}",
        f"env file:  {launch.env_dir / 'sbxenv.yaml'}",
        f"context:   {launch.context} (read-only)",
        "github:    token configured" if launch.github_token is not None else "github:    no token",
    )
    return "\n".join(f"==> {note}" for note in notes)


def run(launch: Launch) -> NoReturn:
    """Prepare the sandbox and replace this process with ``sbx env run``.

    Raises SandboxError if anything before the hand-over fails.
    """
    host = Host(os.getuid())
    socket = host.socket_path(SOCKETS_DIR, launch.name)
    ssh_agent = SshAgent(host, socket)
    env = Sbx.process_env(host.environ(), socket)
    sbx = Sbx(host, env, launch.name, launch.env_dir)
    host.ensure_private_dir(socket.parent)
    prepare(launch, host, ssh_agent, sbx)
    print(description(launch, socket), file=sys.stderr)
    host.exec(sbx.run_args(launch.agent_args), env)
