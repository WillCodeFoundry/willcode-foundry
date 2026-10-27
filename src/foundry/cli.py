"""The foundry command: one subcommand per module in foundry.commands."""

import argparse
import sys
from collections.abc import Callable, Sequence

from agent_runtime.git import GitError
from foundry.agent_sandbox import SandboxError
from foundry.commands import prune, repo, run, skills, task
from foundry.errors import FoundryError

COMMANDS = (run, task, repo, prune, skills)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundry", description="Run coding agents in sandboxes, one role per task.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        command.add_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Commands either return an exit code or replace this process; errors are reported here only."""
    args = build_parser().parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.func
    try:
        return handler(args)
    except (FoundryError, SandboxError, GitError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
