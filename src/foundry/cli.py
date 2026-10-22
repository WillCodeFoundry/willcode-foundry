"""The foundry command: one subcommand per module in foundry.commands."""

import argparse
import sys
from collections.abc import Sequence

from foundry.agent_sandbox import SandboxError
from foundry.commands import protect, run
from foundry.errors import FoundryError

COMMANDS = (run, protect)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundry", description="Run coding agents in sandboxes, one role per task.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        command.add_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Commands either return an exit code or replace this process; errors are reported here only."""
    argv = list(sys.argv[1:] if argv is None else argv)
    split_at = argv.index("--") if "--" in argv else len(argv)
    foundry_args, agent_args = argv[:split_at], tuple(argv[split_at + 1 :])
    args = build_parser().parse_args(foundry_args)
    try:
        return int(args.func(args, agent_args))
    except (FoundryError, SandboxError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
