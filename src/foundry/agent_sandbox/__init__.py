"""Run one Docker Sandbox (sbx) safely, and prune what stopped or removed sandboxes leave behind.

A launch gets a private ssh-agent, a read-only agent kit and verified keys.

Imports nothing from the rest of ``foundry``; it could be lifted out unchanged.
tests/agent_sandbox/test_boundary.py checks that.
"""

from foundry.agent_sandbox.definition import SandboxDefinition
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.launcher import LaunchRequest, launch
from foundry.agent_sandbox.pruning import Pruned, prune

__all__ = ["LaunchRequest", "Pruned", "SandboxDefinition", "SandboxError", "launch", "prune"]
