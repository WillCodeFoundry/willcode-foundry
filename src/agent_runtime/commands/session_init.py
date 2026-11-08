"""`session-init`: what the launcher runs inside the sandbox, as the agent user, before the agent starts.

Owns both ends of the sudo call into root mode: the call is made here, and `harden` is what it runs.
"""

import subprocess
from pathlib import Path

from agent_runtime import contract, hardening, session_init
from agent_runtime.agent_kit import AgentKit
from agent_runtime.commands import check_hardening, progress_on_stdout


def main() -> int:
    """Composition root: this sandbox's machine, and root mode through sudo, passed to session_init.init."""
    variables = contract.read_session_variables()
    with progress_on_stdout():
        outcome = session_init.init(variables, hardening.SANDBOX, _through_sudo)
    return report(outcome)


def report(outcome: session_init.RootModeFailed | session_init.Checked) -> int:
    """Print what agent mode found, and return the exit code. A failed root mode has already said why, so its exit
    code is passed on without a word."""
    match outcome:
        case session_init.RootModeFailed(exit_code=exit_code):
            return exit_code
        case session_init.Checked(can_still=can_still):
            return check_hardening.report(can_still)


def _through_sudo(machine: hardening.Machine, agent_kit_dir: Path) -> int:
    """Root mode through sudo, keeping AGENT_KIT_DIR alone of the environment, running the runtime from the
    read-only kit, isolated."""
    return subprocess.run(_root_command(machine.sudo, agent_kit_dir), check=False).returncode


def _root_command(sudo: str, agent_kit_dir: Path) -> list[str]:
    return [sudo, f"--preserve-env={contract.KIT_DIR}", *AgentKit(agent_kit_dir).runtime_command("harden")]
