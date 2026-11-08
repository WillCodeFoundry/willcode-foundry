"""`harden`: root mode, what session-init runs as root through sudo. sudo passes AGENT_KIT_DIR alone, and sets
SUDO_USER."""

import os

from agent_runtime import hardening
from agent_runtime.commands import read_agent_kit_dir


def main() -> None:
    """Composition root: harden the sandbox this runs in, for the user sudo was called from."""
    sudo_user = os.environ.get("SUDO_USER", "")
    hardening.harden(read_agent_kit_dir(), sudo_user, hardening.SANDBOX)
    print(
        "harden: managed settings installed, their hooks' runtime linked; Docker socket made root-only; root's "
        f"password locked and sudo disabled for {sudo_user}"
    )
