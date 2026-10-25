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

from foundry.agent_sandbox.definition import SandboxDefinition
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import SystemHost
from foundry.agent_sandbox.sandbox import Sandbox, SbxCli, list_live_sandboxes
from foundry.agent_sandbox.ssh_agent import SshAgent, SshAgentRegistry


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


def launch(request: LaunchRequest) -> NoReturn:
    """Prepare the sandbox and replace this process with the agent's session in it.

    Composition root. Raises SandboxError if anything before the hand-over fails.
    """
    definition = SandboxDefinition.read(request.definition_dir)
    host = SystemHost()
    ssh_agent_registry = SshAgentRegistry(host, uid=os.getuid())
    ssh_agent = ssh_agent_registry.ssh_agent(definition.name)
    sandbox = SbxCli(
        host,
        sandbox_name=definition.name,
        definition_dir=request.definition_dir,
        ssh_agent_socket_path=ssh_agent.socket_path,
    )
    if pruned_sandboxes := ssh_agent_registry.prune(live_sandboxes=list_live_sandboxes(host)):
        print(
            f"==> killed the ssh-agents of stopped or removed sandboxes: {', '.join(pruned_sandboxes)}", file=sys.stderr
        )
    prepare(request, definition, ssh_agent, sandbox)
    print(launch_summary(request, definition, ssh_agent.socket_path), file=sys.stderr)
    sandbox.attach()


def prepare(request: LaunchRequest, definition: SandboxDefinition, ssh_agent: SshAgent, sandbox: Sandbox) -> None:
    """Everything up to, but not including, attaching the agent."""
    _require_safe_layout(request, definition)
    ssh_agent.ensure_running()
    ssh_agent.replace_keys([request.ssh_key_path])
    sandbox.ensure_running()
    sandbox.give_github_ssh_access()
    sandbox.set_github_token_file(request.github_token_path)
    _require_forwarded_keys(ssh_agent, sandbox)
    if request.init_command:
        _run_init(sandbox, request.init_command)


def launch_summary(request: LaunchRequest, definition: SandboxDefinition, ssh_agent_socket_path: Path) -> str:
    """The lines launch prints before handing over: what the sandbox was given."""
    notes = (
        f"ssh-agent:  {ssh_agent_socket_path}",
        f"key:        {request.ssh_key_path}",
        f"sandbox:    {definition.name}",
        f"definition: {request.definition_dir / SandboxDefinition.FILE_NAME}",
        f"agent kit:  {definition.agent_kit_dir} (read-only)",
        f"github:     token from {request.github_token_path}"
        if request.github_token_path is not None
        else "github:     no token",
    )
    return "\n".join(f"==> {note}" for note in notes)


def _require_safe_layout(request: LaunchRequest, definition: SandboxDefinition) -> None:
    """Refuse a missing file or directory, and layouts that would undo the sandbox's protections."""
    for target_dir, what in ((definition.agent_kit_dir, "agent kit"), (definition.workspace_dir, "workspace")):
        if not target_dir.is_dir():
            raise SandboxError(f"{what} {str(target_dir)!r} is not a directory")
    private_files = {"ssh key": request.ssh_key_path}
    if request.github_token_path is not None:
        private_files["github token file"] = request.github_token_path
    for what, file_path in private_files.items():
        if not file_path.is_file():
            raise SandboxError(f"{what} {str(file_path)!r} is not a file")
    if ":" in str(definition.agent_kit_dir):
        raise SandboxError(f"agent kit directory {str(definition.agent_kit_dir)!r} contains ':'")
    for private_path in private_files.values():
        if private_path.is_relative_to(definition.agent_kit_dir):
            raise SandboxError(f"{str(private_path)!r} is inside the agent kit, readable by the sandbox")
    if request.definition_dir.is_relative_to(definition.agent_kit_dir):
        raise SandboxError(
            f"sandbox definition {str(request.definition_dir)!r} is inside the agent kit; the sandbox could rewrite it"
        )


def _require_forwarded_keys(ssh_agent: SshAgent, sandbox: Sandbox) -> None:
    """The sandbox must see exactly the keys we loaded, whatever sbx's settings claim."""
    expected = ssh_agent.key_fingerprints()
    if not expected:  # a sandbox with an empty ssh-agent would otherwise match
        raise SandboxError(f"the ssh-agent at {ssh_agent.socket_path} holds no keys after loading them")
    seen = sandbox.forwarded_key_fingerprints()
    if seen != expected:
        found = "no ssh-agent" if seen is None else f"keys {sorted(seen)}"
        raise SandboxError(
            f"the sandbox sees {found}, expected {sorted(expected)}.\n"
            "  check: sbx settings get ssh.agentForwardingEnabled  (must be true)\n"
            "         sbx settings get ssh.agentSocketPath         (must be empty)\n"
            "  then:  sbx daemon restart"
        )


def _run_init(sandbox: Sandbox, init_command: Sequence[str]) -> None:
    result = sandbox.run(init_command)
    if result.returncode != 0:
        raise SandboxError(f"init failed ({' '.join(init_command)}):\n{result.stdout}{result.stderr}".rstrip())
