"""Prepare a sandbox for an agent run, in order: setup as the agent, root mode on the first launch, then agent mode.

Idempotent: safe to run again on a re-attached sandbox. What each hardening mode does is agent_runtime.hardening's;
the sudo call into root mode is agent_runtime.commands.session_init's, which passes it in as ``run_as_root``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agent_runtime import contract, hardening, session_setup

RunAsRoot = Callable[[hardening.Machine, Path], int]
"""Runs root mode for the kit at the Path, as root, and returns its exit code."""


@dataclass(frozen=True)
class RootModeFailed:
    """Root mode exited non-zero, so the launch stops before agent mode. Root mode has already said why."""

    exit_code: int


@dataclass(frozen=True)
class Checked:
    """Agent mode ran."""

    can_still: list[str]
    """What the agent can still do that hardening should stop; empty when the sandbox is hardened."""


def init(
    variables: contract.SessionVariables, machine: hardening.Machine, run_as_root: RunAsRoot
) -> RootModeFailed | Checked:
    """Set up as the agent; harden as root on the first launch, while sudo still works; check the hardening as the
    agent on every launch, with the groups sbx gives it. Raises SetupRefused when setup can't go ahead."""
    session_setup.set_up(variables)
    if hardening.can_sudo(machine.sudo) and (exit_code := run_as_root(machine, variables.agent_kit_dir)) != 0:
        return RootModeFailed(exit_code)
    return Checked(hardening.check(variables.agent_kit_dir, machine))
