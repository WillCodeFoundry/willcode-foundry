"""Launch one sandbox from its definition, with its own ssh-agent.

Imports nothing from the rest of foundry: it is given a directory holding the
sandbox definition, a private key, and what to run before handing the
terminal to the agent. The sandbox's name and agent kit come from the
definition.
"""

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from foundry.agent_sandbox import definition
from foundry.agent_sandbox.definition import DEFINITION_FILE_NAME, SandboxDefinition
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import Host, SystemHost
from foundry.agent_sandbox.sbx import Sbx
from foundry.agent_sandbox.ssh_agent import SshAgent, socket_path


@dataclass(frozen=True)
class LaunchRequest:
    """Everything the launcher needs for one launch. Every path is absolute."""

    definition_dir: Path
    """Directory holding the sandbox definition; also where sbx env commands are pointed."""
    ssh_key_path: Path
    init_command: tuple[str, ...] = ()
    """Run inside the sandbox before the agent starts; the launch aborts if it fails."""
    github_token_path: Path | None = None
    """File holding a GitHub token for the sandbox; sbx reads it on the host when needed."""
    agent_args: tuple[str, ...] = ()


def require_safe_paths(agent_kit_dir: Path, definition_dir: Path, private_paths: Sequence[Path]) -> None:
    """Refuse layouts that would undo the sandbox's protections."""
    if ":" in str(agent_kit_dir):
        raise SandboxError(f"agent kit directory {str(agent_kit_dir)!r} contains ':'")
    for private_path in private_paths:
        if private_path.is_relative_to(agent_kit_dir):
            raise SandboxError(f"{str(private_path)!r} is inside the agent kit, readable by the sandbox")
    if definition_dir.is_relative_to(agent_kit_dir):
        raise SandboxError(
            f"sandbox definition {str(definition_dir)!r} is inside the agent kit; the sandbox could rewrite it"
        )


def require_forwarded_keys(ssh_agent: SshAgent, sbx: Sbx) -> None:
    """The sandbox must see exactly the keys we loaded, whatever sbx's settings claim."""
    expected = ssh_agent.list_key_fingerprints()
    if not expected:  # a sandbox with an empty agent would otherwise match
        raise SandboxError(f"the ssh-agent at {ssh_agent.socket_path} holds no keys after loading them")
    seen = sbx.agent_fingerprints()
    if seen != expected:
        found = "no ssh-agent" if seen is None else f"keys {sorted(seen)}"
        raise SandboxError(
            f"the sandbox sees {found}, expected {sorted(expected)}.\n"
            "  check: sbx settings get ssh.agentForwardingEnabled  (must be true)\n"
            "         sbx settings get ssh.agentSocketPath         (must be empty)\n"
            "  then:  sbx daemon restart"
        )


def prepare(request: LaunchRequest, sandbox: SandboxDefinition, host: Host, ssh_agent: SshAgent, sbx: Sbx) -> None:
    """Everything up to, but not including, attaching the agent."""
    host.require_dir(sandbox.agent_kit_dir, "agent kit")
    host.require_file(request.ssh_key_path, "ssh key")
    private_paths = [request.ssh_key_path]
    if request.github_token_path is not None:
        host.require_file(request.github_token_path, "github token file")
        private_paths.append(request.github_token_path)
    require_safe_paths(sandbox.agent_kit_dir, request.definition_dir, private_paths)

    ssh_agent.ensure_running()
    ssh_agent.replace_keys([request.ssh_key_path])

    if not sbx.start_if_exists():
        sbx.create()
    sbx.ensure_github_ssh_allowed()
    sbx.ensure_known_hosts()
    # Clear first: a token from an earlier launch must not outlive its file.
    sbx.clear_github_token()
    if request.github_token_path is not None:
        sbx.set_github_token_source(request.github_token_path)
    require_forwarded_keys(ssh_agent, sbx)

    if request.init_command:
        result = sbx.exec_in_sandbox(*request.init_command)
        if result.returncode != 0:
            raise SandboxError(
                f"init failed ({' '.join(request.init_command)}):\n{result.stdout}{result.stderr}".rstrip()
            )


def describe(request: LaunchRequest, sandbox: SandboxDefinition, ssh_agent_socket_path: Path) -> str:
    notes = (
        f"ssh-agent:  {ssh_agent_socket_path}",
        f"key:        {request.ssh_key_path}",
        f"sandbox:    {sandbox.name}",
        f"definition: {request.definition_dir / DEFINITION_FILE_NAME}",
        f"agent kit:  {sandbox.agent_kit_dir} (read-only)",
        f"github:     token from {request.github_token_path}"
        if request.github_token_path is not None
        else "github:     no token",
    )
    return "\n".join(f"==> {note}" for note in notes)


def launch(request: LaunchRequest) -> NoReturn:
    """Prepare the sandbox and replace this process with ``sbx env run``.

    Raises SandboxError if anything before the hand-over fails.
    """
    sandbox = definition.read(request.definition_dir)
    uid = os.getuid()
    host = SystemHost(uid)
    ssh_agent_socket_path = socket_path(sandbox.name, uid)
    ssh_agent = SshAgent(host, ssh_agent_socket_path)
    process_env = Sbx.process_env(host.environ(), ssh_agent_socket_path)
    sbx = Sbx(host, process_env, sandbox.name, request.definition_dir)
    host.ensure_private_dir(ssh_agent_socket_path.parent)
    prepare(request, sandbox, host, ssh_agent, sbx)
    print(describe(request, sandbox, ssh_agent_socket_path), file=sys.stderr)
    host.exec(sbx.attach_command(request.agent_args), process_env)
