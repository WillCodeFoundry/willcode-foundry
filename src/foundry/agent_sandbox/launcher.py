"""Launch one sandbox from its definition, with its own ssh-agent: prune remnants, provision the sandbox, attach the
agent, then check the checkout status once the agent run ends.

Imports nothing from the rest of foundry. It is given a dir holding the sandbox definition, a private key, and
what to run before attaching the agent and after its run. The sandbox's name and agent kit come from the definition.
"""

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from foundry.agent_sandbox.definition import SandboxDefinition
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import SystemHost
from foundry.agent_sandbox.pruning import prune
from foundry.agent_sandbox.sandbox import Sandbox, SbxCli
from foundry.agent_sandbox.ssh_agent import SshAgent, SshAgentRegistry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LaunchRequest:
    """Everything the launcher needs for one launch. Every path is absolute."""

    definition_dir: Path
    """Directory holding the sandbox definition; also where sbx env commands are pointed."""
    ssh_key_path: Path
    checkout_status_command: tuple[str, ...]
    """Run inside the sandbox after the agent run: it prints the checkout status, and exits 0 when both checkouts are
    saved."""
    init_command: tuple[str, ...] = ()
    """Run inside the sandbox before the agent starts; the launch aborts if it fails."""
    github_token_path: Path | None = None
    """File holding a GitHub token for the sandbox; sbx reads it on the host when needed."""
    model: str | None = None
    """The model the agent runs on, given to it at each attach; None for its default. Not part of the sandbox."""


@dataclass(frozen=True)
class CheckoutStatus:
    """Both checkouts' unsaved work after an agent run, that both are saved, or why it can't tell."""

    text: str
    """What to show the human, one or more lines."""
    exit_code: int
    """0 when both checkouts are saved, 1 otherwise."""


def launch(request: LaunchRequest) -> CheckoutStatus:
    """Prune remnants, provision this sandbox, attach an agent run in it on this terminal, and return the checkout
    status once the run ends, however it ended.

    Composition root: it builds the real host, ssh-agent and sbx client, and passes them to provision_sandbox.
    Shows each remnant pruned and the launch summary as progress, and the init command's output as detail.
    Raises SandboxError if anything before attaching fails, and then reports no checkout status.
    """
    for remnant in prune():
        _LOGGER.info("pruned the %s of %s", remnant.kind, remnant.sandbox_name)
    definition = SandboxDefinition.read(request.definition_dir)
    host = SystemHost()
    ssh_agent = SshAgentRegistry(host, uid=os.getuid()).ssh_agent(definition.name)
    sandbox = SbxCli(
        host,
        sandbox_name=definition.name,
        definition_dir=request.definition_dir,
        ssh_agent_socket_path=ssh_agent.socket_path,
    )
    for line in provision_sandbox(request, definition, ssh_agent, sandbox).splitlines():
        _LOGGER.debug("init: %s", line)
    for line in launch_summary(request, definition, ssh_agent.socket_path):
        _LOGGER.info("%s", line)
    sandbox.attach(request.model)
    return check_checkout_status(request, sandbox)


def check_checkout_status(request: LaunchRequest, sandbox: Sandbox) -> CheckoutStatus:
    """The checkout status, from the request's checkout status command, run in the sandbox.

    "can't tell", without running it, when the sandbox isn't running, since running anything would start it, or when
    an agent still runs in it. A SandboxError from any of it is "can't tell" too, with its message.
    """
    try:
        sandbox_name = SandboxDefinition.read(request.definition_dir).name
        if not sandbox.is_running():
            return _unknown_status(f"sandbox {sandbox_name} is not running")
        if sandbox.is_agent_running():
            return _unknown_status(f"an agent is still running in sandbox {sandbox_name}; {sandbox.stop_hint()}")
        result = sandbox.run(request.checkout_status_command)
    except SandboxError as error:
        return _unknown_status(str(error))
    return CheckoutStatus(
        text=f"{result.stdout}{result.stderr}".rstrip("\n"), exit_code=0 if result.returncode == 0 else 1
    )


def _unknown_status(reason: str) -> CheckoutStatus:
    return CheckoutStatus(text=f"can't tell: {reason}", exit_code=1)


def provision_sandbox(
    request: LaunchRequest, definition: SandboxDefinition, ssh_agent: SshAgent, sandbox: Sandbox
) -> str:
    """Bring the sandbox to the state the agent starts in, creating it if missing: its ssh-agent holding only the
    role's key, GitHub reachable over SSH, the token set, the forwarded keys checked, then the init command run.
    Returns what the init command printed. Raises SandboxError if any of it fails, or if an agent already runs in the
    sandbox, which a second one would work beside."""
    _require_safe_layout(request, definition)
    ssh_agent.ensure_running()
    ssh_agent.replace_keys([request.ssh_key_path])
    sandbox.ensure_running()
    if sandbox.is_agent_running():
        raise SandboxError(
            f"an agent is already running in sandbox {definition.name}, so no second one is started; "
            f"{sandbox.stop_hint()}"
        )
    sandbox.give_github_ssh_access()
    sandbox.set_github_token_file(request.github_token_path)
    _require_forwarded_keys(ssh_agent, sandbox)
    return _run_init(sandbox, request.init_command) if request.init_command else ""


def launch_summary(
    request: LaunchRequest, definition: SandboxDefinition, ssh_agent_socket_path: Path
) -> tuple[str, ...]:
    """The progress lines launch shows before attaching: what the sandbox was given."""
    return (
        f"ssh-agent:  {ssh_agent_socket_path}",
        f"key:        {request.ssh_key_path}",
        f"sandbox:    {definition.name}",
        f"definition: {request.definition_dir / SandboxDefinition.FILE_NAME}",
        f"agent kit:  {definition.agent_kit_dir} (read-only)",
        f"github:     token from {request.github_token_path}"
        if request.github_token_path is not None
        else "github:     no token",
        f"model:      {request.model or 'the agent default'}",
    )


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
        seen_text = "no ssh-agent" if seen is None else f"keys {sorted(seen)}"
        raise SandboxError(
            f"the sandbox sees {seen_text}, expected {sorted(expected)}.\n"
            "  check: sbx settings get ssh.agentForwardingEnabled  (must be true)\n"
            "         sbx settings get ssh.agentSocketPath         (must be empty)\n"
            "  then:  sbx daemon restart"
        )


def _run_init(sandbox: Sandbox, init_command: Sequence[str]) -> str:
    result = sandbox.run(init_command)
    if result.returncode != 0:
        raise SandboxError(f"init failed ({' '.join(init_command)}):\n{result.stdout}{result.stderr}".rstrip())
    return result.stdout
