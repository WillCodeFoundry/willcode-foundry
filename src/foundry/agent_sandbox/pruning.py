"""Pruning the remnants of stopped or removed sandboxes on this machine."""

import os
from dataclasses import dataclass
from enum import StrEnum

from foundry.agent_sandbox.host import SystemHost
from foundry.agent_sandbox.sandbox import list_live_sandboxes
from foundry.agent_sandbox.ssh_agent import SshAgentRegistry


class RemnantKind(StrEnum):
    """What a remnant is. A new kind of remnant adds a member here, not a new return type."""

    SSH_AGENT = "ssh-agent"


@dataclass(frozen=True)
class Remnant:
    """Something of a sandbox that outlived it: every remnant belongs to one sandbox."""

    sandbox_name: str
    kind: RemnantKind


def prune() -> list[Remnant]:
    """Composition root: prune the remnants of every sandbox that is stopped or removed, and return them.

    sbx lists all its user's sandboxes, so other foundries' live sandboxes keep their remnants.
    """
    host = SystemHost()
    ssh_agent_registry = SshAgentRegistry(host, uid=os.getuid())
    return [
        Remnant(sandbox_name, RemnantKind.SSH_AGENT)
        for sandbox_name in ssh_agent_registry.prune(live_sandboxes=list_live_sandboxes(host))
    ]
