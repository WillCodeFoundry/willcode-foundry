"""Prepare a sandbox for an agent session: what the launcher runs inside the sandbox, as the agent user,
before the agent starts. Idempotent: safe to run again on a re-attached sandbox.

Owns both ends of the launch's handoff to root. As the agent, session_init probes sudo and, on the first
launch, while it still works, runs root mode through it, passing AGENT_KIT_DIR alone. Root mode's entry,
root_mode, is what that command reaches: it reads AGENT_KIT_DIR and SUDO_USER and hardens. Agent mode's entry,
agent_mode, reads AGENT_KIT_DIR alone and verifies. What each mode does is agent_runtime.harden's.
"""

import os
import subprocess
from pathlib import Path

from agent_runtime import contract, harden, session_setup


def session_init(env: contract.Environ | None = None) -> int:
    """Set up as the agent; harden as root on the first launch; verify as the agent on every launch.

    Hardening runs while sudo still exists, so nothing after it may need root. The verify runs as the agent
    itself, with the groups sbx gives it: the launch stops unless the agent can't become root.
    """
    environ = env or contract.read_environ()
    if (returncode := session_setup.session_setup(environ)) != 0:
        return returncode
    sudo = harden.SANDBOX.sudo
    if harden.can_sudo(sudo):
        hardened = subprocess.run(_root_command(sudo, environ.kit_dir), check=False)
        if hardened.returncode != 0:
            return hardened.returncode
    return harden.verify(environ.kit_dir)


def root_mode() -> int:
    """`harden`: what the root command runs. sudo passes AGENT_KIT_DIR alone, and sets SUDO_USER."""
    return harden.harden(_read_kit_dir(), os.environ.get("SUDO_USER", ""))


def agent_mode() -> int:
    """`harden --verify`: the check session_init runs after root mode, given AGENT_KIT_DIR alone."""
    return harden.verify(_read_kit_dir())


def _root_command(sudo: str, kit_dir: Path) -> list[str]:
    """Root mode through sudo, keeping AGENT_KIT_DIR alone of the environment, running the runtime from the
    read-only kit, isolated."""
    return [sudo, f"--preserve-env={contract.KIT_DIR}", *contract.command(kit_dir, "harden")]


def _read_kit_dir() -> Path:
    """AGENT_KIT_DIR, the one session variable root mode is given; MissingVariables, which __main__ reports,
    when it isn't set."""
    kit_dir = os.environ.get(contract.KIT_DIR)
    if not kit_dir:
        raise contract.MissingVariables([contract.KIT_DIR])
    return Path(kit_dir)
