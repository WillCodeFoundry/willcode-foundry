"""`check-hardening`: agent mode on its own, given AGENT_KIT_DIR alone. session-init runs the same check in-process."""

import sys

from agent_runtime import hardening
from agent_runtime.commands import read_agent_kit_dir


def main() -> int:
    """Composition root: check the sandbox this runs in, and report it."""
    return report(hardening.check(read_agent_kit_dir(), hardening.SANDBOX))


def report(can_still: list[str]) -> int:
    """Print what agent mode found, and return the exit code: 1 while the agent can still do anything on the list."""
    if can_still:
        indented = "".join(f"  {line}\n" for line in can_still)
        sys.stderr.write(
            f"check-hardening: not starting the agent; it can still:\n{indented}"
            "This sandbox needs recreating: see Recreating a sandbox in the foundry's README.\n"
        )
        return 1
    print("check-hardening: hardened")
    return 0
