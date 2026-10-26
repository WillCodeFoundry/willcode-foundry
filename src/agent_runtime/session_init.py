"""Prepare a sandbox for an agent session: what the launcher runs inside the sandbox, as the agent user,
before the agent starts. Idempotent: safe to run again on a re-attached sandbox."""

import subprocess

from agent_runtime import contract, harden, session_setup


def session_init(env: contract.Environ | None = None) -> int:
    """Set up as the agent; harden as root on the first launch; verify as the agent on every launch.

    Hardening runs while sudo still exists, so nothing after it may need root. The verify runs as the agent
    itself, with the groups sbx gives it: the launch stops unless the agent can't become root.
    """
    environ = env or contract.read_environ()
    if (returncode := session_setup.session_setup(environ)) != 0:
        return returncode
    if harden.can_sudo():
        # Root is given AGENT_KIT_DIR alone, and runs the runtime from the read-only kit, isolated.
        root_command = ["sudo", f"--preserve-env={contract.KIT_DIR}", *contract.command(environ.kit_dir, "harden")]
        hardened = subprocess.run(root_command, check=False)
        if hardened.returncode != 0:
            return hardened.returncode
    return harden.verify(environ.kit_dir)
