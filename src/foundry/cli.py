"""The foundry command: one subcommand per module in foundry.commands.

A command prints its result, such as the tasks it created. Progress, such as a new session or a pruned remnant, goes
to the ``foundry`` logger from the module where it happens. main shows it on stderr as ``==>`` lines, at INFO, and
with ``-v`` the detail at DEBUG too.
"""

import argparse
import logging
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager

from agent_runtime.git import GitError
from foundry.agent_sandbox import SandboxError
from foundry.commands import prune, repo, run, skills, task
from foundry.errors import FoundryError

COMMANDS = (run, task, repo, prune, skills)
_LOGGER = logging.getLogger("foundry")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundry", description="Run coding agents in sandboxes, one role per task.")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="also show the detail of each step, such as session-init's output"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        command.add_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Commands either return an exit code or replace this process; errors are reported here only."""
    args = build_parser().parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.func
    with _progress_on_stderr(verbose=args.verbose):
        try:
            return handler(args)
        except (FoundryError, SandboxError, GitError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1


@contextmanager
def _progress_on_stderr(*, verbose: bool) -> Iterator[None]:
    """Show progress on stderr while one command runs, and detail too when ``verbose``.

    The handler and level are removed afterwards, so nothing carries over to the next call of main.
    """
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("==> %(message)s"))
    previous_level = _LOGGER.level
    _LOGGER.addHandler(stderr_handler)
    _LOGGER.setLevel(logging.DEBUG if verbose else logging.INFO)
    try:
        yield
    finally:
        _LOGGER.removeHandler(stderr_handler)
        _LOGGER.setLevel(previous_level)


if __name__ == "__main__":
    sys.exit(main())
