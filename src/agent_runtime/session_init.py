"""Prepare a sandbox for an agent session: what the launcher runs inside the sandbox, as the agent user, before
the agent starts. Idempotent: safe to run again on a re-attached sandbox. Owns both ends of the handoff to root;
what each hardening mode does is agent_runtime.harden's.
"""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from agent_runtime import contract, session_setup
from agent_runtime import harden as hardening
from agent_runtime.agent_kit import AgentKit

RunAsRoot = Callable[[hardening.Machine, Path], int]
"""Runs root mode for the kit at the Path, as root, and returns its exit code."""


def session_init(
    session: contract.Environ | None = None,
    machine: hardening.Machine = hardening.SANDBOX,
    run_as_root: RunAsRoot | None = None,
) -> int:
    """Set up as the agent; harden as root on the first launch, while sudo still works; check the hardening as the
    agent on every launch, with the groups sbx gives it. The launch stops unless the agent can't become root."""
    session = session or contract.read_environ()
    session_setup.session_setup(session)
    if hardening.can_sudo(machine.sudo):
        if (returncode := (run_as_root or _through_sudo)(machine, session.agent_kit_dir)) != 0:
            return returncode
    return _check_hardening(session.agent_kit_dir, machine)


def harden() -> int:
    """`harden`: what the root command runs. sudo passes AGENT_KIT_DIR alone, and sets SUDO_USER."""
    return _harden(_read_agent_kit_dir(), os.environ.get("SUDO_USER", ""), hardening.SANDBOX)


def check_hardening() -> int:
    """`check-hardening`: the check session_init runs after root mode, given AGENT_KIT_DIR alone."""
    return _check_hardening(_read_agent_kit_dir(), hardening.SANDBOX)


def _harden(agent_kit_dir: Path, sudo_user: str, machine: hardening.Machine) -> int:
    hardening.harden(agent_kit_dir, sudo_user, machine)
    print(
        "harden: managed settings installed, their hooks' runtime linked; Docker socket made root-only; root's "
        f"password locked and sudo removed for {sudo_user}"
    )
    return 0


def _check_hardening(agent_kit_dir: Path, machine: hardening.Machine) -> int:
    if failures := hardening.check(agent_kit_dir, machine):
        lines = "".join(f"  {line}\n" for line in failures)
        sys.stderr.write(
            f"check-hardening: not starting the agent; it can still:\n{lines}"
            "This sandbox needs recreating: see Recreating a sandbox in the foundry's README.\n"
        )
        return 1
    print("check-hardening: hardened")
    return 0


def _through_sudo(machine: hardening.Machine, agent_kit_dir: Path) -> int:
    """Root mode through sudo, keeping AGENT_KIT_DIR alone of the environment, running the runtime from the
    read-only kit, isolated."""
    return subprocess.run(_root_command(machine.sudo, agent_kit_dir), check=False).returncode


def _root_command(sudo: str, agent_kit_dir: Path) -> list[str]:
    return [sudo, f"--preserve-env={contract.KIT_DIR}", *AgentKit(agent_kit_dir).command("harden")]


def _read_agent_kit_dir() -> Path:
    """AGENT_KIT_DIR, the one session variable the hardening entries are given."""
    contract.require(os.environ, [contract.KIT_DIR])
    return Path(os.environ[contract.KIT_DIR])
