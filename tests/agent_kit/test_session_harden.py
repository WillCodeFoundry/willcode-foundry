"""agent-kit/bin/session-harden's refusal to run outside a sandbox.

session-harden removes sudo from the machine it runs on, so it is only run as far as its refusal.
"""

import os
import subprocess
from pathlib import Path

import pytest

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"


@pytest.mark.parametrize("sudo_user", [None, "root", "will"])
def test_session_harden_refuses_outside_a_sandbox_before_changing_anything(sudo_user: str | None) -> None:
    # Never run with SUDO_USER=agent: as root, that would harden this machine.
    env = {"PATH": os.environ["PATH"], "AGENT_KIT_DIR": str(AGENT_KIT_PATH)}
    if sudo_user is not None:
        env["SUDO_USER"] = sudo_user
    result = subprocess.run(
        [str(AGENT_KIT_PATH / "bin" / "session-harden")], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert "only runs inside a foundry sandbox" in result.stderr
