"""Run one Docker Sandbox (sbx) safely, and prune the remnants of stopped or removed sandboxes.

A launch gets a private ssh-agent, a read-only agent kit and verified keys.

Imports nothing from the rest of ``foundry``; it could be lifted out unchanged.
tests/agent_sandbox/test_boundary.py checks that.
"""

from foundry.agent_sandbox.definition import MAX_SANDBOX_NAME_LENGTH, SandboxDefinition, is_valid_sandbox_name
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.launcher import LaunchRequest, launch
from foundry.agent_sandbox.pruning import Remnant, RemnantKind, prune

__all__ = [
    "MAX_SANDBOX_NAME_LENGTH",
    "LaunchRequest",
    "Remnant",
    "RemnantKind",
    "SandboxDefinition",
    "SandboxError",
    "is_valid_sandbox_name",
    "launch",
    "prune",
]
