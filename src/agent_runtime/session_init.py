"""Prepare a sandbox for an agent session: what the launcher runs inside the sandbox, as the agent user,
before the agent starts. Idempotent: safe to run again on a re-attached sandbox."""

import subprocess

from agent_runtime import contract, session_setup


def session_init(env: contract.Environ | None = None) -> int:
    """Set up as the agent; harden as root on the first launch; verify as the agent on every launch.

    Hardening runs while sudo still exists, so nothing after it may need root. The verify runs as the agent
    itself, with the groups sbx gives it: the launch stops unless the agent can't become root.
    """
    environ = env or contract.read_environ()
    if (returncode := session_setup.session_setup(environ)) != 0:
        return returncode
    harden = str(environ.kit_dir / "bin" / "session-harden")
    if _can_sudo():
        hardened = subprocess.run(["sudo", f"--preserve-env={contract.KIT_DIR}", harden], check=False)
        if hardened.returncode != 0:
            return hardened.returncode
    return subprocess.run([harden, "--verify"], check=False).returncode


def _can_sudo() -> bool:
    try:
        return subprocess.run(["sudo", "-n", "true"], capture_output=True, check=False).returncode == 0
    except FileNotFoundError:
        return False
