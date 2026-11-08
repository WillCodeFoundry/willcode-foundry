"""foundry prune: prune the remnants of stopped or removed sandboxes on this machine."""

import argparse

from foundry import agent_sandbox


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "prune",
        help="prune the remnants of stopped or removed sandboxes",
        description=(
            "Prune the remnants of sandboxes that are stopped or removed: their ssh-agents. "
            "foundry run does the same before each launch; this does it without launching."
        ),
    )
    parser.set_defaults(func=main)


def main(_args: argparse.Namespace) -> int:
    """Composition root: prune what agent_sandbox owns, and report it."""
    print("\n".join(report(agent_sandbox.prune())))
    return 0


def report(pruned: list[agent_sandbox.Remnant]) -> list[str]:
    """The lines prune prints: each remnant it pruned, or that there was nothing to prune."""
    lines = [f"pruned the {remnant.kind} of {remnant.sandbox_name}" for remnant in pruned]
    return lines or ["nothing to prune"]
