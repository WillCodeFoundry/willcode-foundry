"""The foundry command: one subcommand per module in foundry.commands."""

import argparse
import sys
from collections.abc import Sequence

from foundry.agent_sandbox import SandboxError
from foundry.commands import run
from foundry.errors import FoundryError

COMMANDS = (run,)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundry", description="Run coding agents in sandboxes, one role per task.")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        command.add_parser(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Commands either return an exit code or replace this process; errors are reported here only."""
    argv = list(sys.argv[1:] if argv is None else argv)
    split = argv.index("--") if "--" in argv else len(argv)
    own, passthrough = argv[:split], tuple(argv[split + 1 :])
    args = build_parser().parse_args(own)
    try:
        return int(args.func(args, passthrough))
    except (FoundryError, SandboxError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
