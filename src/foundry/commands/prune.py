"""foundry prune: clean up what stopped or removed sandboxes leave behind on this machine."""

import argparse

from foundry import agent_sandbox


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "prune",
        help="clean up what stopped or removed sandboxes leave behind",
        description=(
            "Kill the ssh-agents of sandboxes that are stopped or removed. "
            "foundry run does the same before each launch; this does it without launching."
        ),
    )
    parser.set_defaults(func=main)


def main(args: argparse.Namespace) -> int:
    """Composition root: prune what agent_sandbox owns, and report it."""
    print("\n".join(report(agent_sandbox.prune())))
    return 0


def report(pruned: agent_sandbox.Pruned) -> list[str]:
    """The lines prune prints: each thing it removed, or that there was nothing to remove."""
    lines = [f"killed the ssh-agent of {sandbox_name}" for sandbox_name in pruned.ssh_agents]
    return lines or ["nothing to prune"]
