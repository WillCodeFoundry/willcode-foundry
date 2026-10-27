"""Cleaning up what stopped or removed sandboxes leave behind on this machine."""

import os
from dataclasses import dataclass

from foundry.agent_sandbox.host import SystemHost
from foundry.agent_sandbox.sandbox import list_live_sandboxes
from foundry.agent_sandbox.ssh_agent import SshAgentRegistry


@dataclass(frozen=True)
class Pruned:
    """What prune removed. A new kind of cleanup adds a field, not a new return type."""

    ssh_agents: list[str]
    """Names of the sandboxes whose ssh-agents were killed."""


def live_sandboxes() -> set[str]:
    """Composition root: the names of this machine's sandboxes that aren't stopped, as sbx lists them."""
    return list_live_sandboxes(SystemHost())


def prune() -> Pruned:
    """Composition root: everything agent_sandbox can clean up on this machine.

    sbx lists all its user's sandboxes, so other foundry instances' live sandboxes keep their agents.
    """
    host = SystemHost()
    ssh_agent_registry = SshAgentRegistry(host, uid=os.getuid())
    return Pruned(ssh_agents=ssh_agent_registry.prune(live_sandboxes=list_live_sandboxes(host)))
