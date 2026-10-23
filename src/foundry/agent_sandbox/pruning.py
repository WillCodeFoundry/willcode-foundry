"""Cleaning up what stopped or removed sandboxes leave behind on this machine."""

import os
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from foundry.agent_sandbox.host import Host, SystemHost
from foundry.agent_sandbox.sbx import list_live_sandboxes
from foundry.agent_sandbox.ssh_agent import AGENT_SOCKETS_DIR, kill_ssh_agents


@dataclass(frozen=True)
class Pruned:
    """What prune removed. A new kind of cleanup adds a field, not a new return type."""

    ssh_agents: list[str]
    """Names of the sandboxes whose ssh-agents were killed."""


def kill_unused_ssh_agents(
    host: Host,
    uid: int,
    sockets_dir: Path,
    process_env: Mapping[str, str],
    *,
    also_keep: Collection[str] = (),
) -> list[str]:
    """Kill the ssh-agents of sandboxes that aren't live, except ``also_keep``'s; return their names.

    sbx lists all its user's sandboxes, so other foundry instances' live sandboxes keep their agents.
    """
    return kill_ssh_agents(host, uid, sockets_dir, keep=list_live_sandboxes(host, process_env) | set(also_keep))


def prune() -> Pruned:
    """Composition root: everything agent_sandbox can clean up on this machine."""
    host = SystemHost()
    return Pruned(ssh_agents=kill_unused_ssh_agents(host, os.getuid(), AGENT_SOCKETS_DIR, host.environ()))
