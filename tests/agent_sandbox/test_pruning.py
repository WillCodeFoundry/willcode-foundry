"""Pruning: what agent_sandbox cleans up, against a FakeHost with canned sbx and process listings."""

import pytest

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.pruning import kill_unused_ssh_agents
from foundry.agent_sandbox.ssh_agent import agent_socket_path

UID = 1000
SBX_LS = ("sbx", "ls", "--json")
SBX_LS_JSON = """{
  "sandboxes": [
    {"name": "dev-p-running", "id": "1", "agent": "claude", "status": "running", "workspaces": []},
    {"name": "dev-p-stopped", "id": "2", "agent": "claude", "status": "stopped", "workspaces": []},
    {"name": "dev-p-launching", "id": "3", "agent": "claude", "status": "stopped", "workspaces": []}
  ]
}"""


def agent_processes(*sandbox_names: str) -> list[tuple[int, str]]:
    return [
        (101 + index, f"ssh-agent -a {agent_socket_path(name, UID)} -s") for index, name in enumerate(sandbox_names)
    ]


def test_agents_of_stopped_or_removed_sandboxes_are_killed(host) -> None:
    host.responses = {SBX_LS: SBX_LS_JSON}
    host.processes = agent_processes("dev-p-running", "dev-p-stopped", "dev-p-removed")

    killed = kill_unused_ssh_agents(host, UID, {})

    assert killed == ["dev-p-removed", "dev-p-stopped"]
    assert sorted(host.killed) == [102, 103]


def test_also_keep_spares_a_sandbox_that_is_not_live_yet(host) -> None:
    host.responses = {SBX_LS: SBX_LS_JSON}
    host.processes = agent_processes("dev-p-launching", "dev-p-stopped")

    killed = kill_unused_ssh_agents(host, UID, {}, also_keep={"dev-p-launching"})

    assert killed == ["dev-p-stopped"]
    assert host.killed == [102]


def test_nothing_is_killed_when_sbx_ls_fails(host) -> None:
    host.responses = {SBX_LS: 1}
    host.processes = agent_processes("dev-p-stopped")

    with pytest.raises(SandboxError, match="sbx ls failed"):
        kill_unused_ssh_agents(host, UID, {})
    assert host.killed == []
