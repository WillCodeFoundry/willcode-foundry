"""The runtime's command line: ``/usr/bin/python3 -IS agent_runtime.pyz <command>``.

The version is checked before anything else is imported, and this file uses only syntax that old
interpreters parse, so a template that ships an older python3 prints what it needs instead of a
SyntaxError from a module further in.
"""

import sys

MINIMUM_PYTHON = (3, 11)

if sys.version_info < MINIMUM_PYTHON:
    needed = ".".join(map(str, MINIMUM_PYTHON))
    found = ".".join(map(str, sys.version_info[:2]))
    sys.stderr.write(f"agent_runtime: needs Python >= {needed}; {sys.executable} is {found}\n")
    sys.exit(1)

import argparse  # noqa: E402
from collections.abc import Callable, Sequence  # noqa: E402

from agent_runtime import claude_hooks, contract, session_init, session_setup  # noqa: E402
from agent_runtime import harden as hardening  # noqa: E402
from agent_runtime.git import GitError  # noqa: E402

COMMANDS: dict[str, tuple[Callable[[], int], str]] = {
    "session-init": (session_init.session_init, "prepare the sandbox: what the launcher runs before the agent"),
    "session-setup": (lambda: _ran(session_setup.session_setup), "the agent user's part of session-init"),
    "harden": (session_init.harden, "as root: harden the sandbox"),
    "check-hardening": (session_init.check_hardening, "as the agent: check the sandbox is hardened"),
}
CLAUDE_HOOKS: dict[str, Callable[[], int]] = {
    "guard-bash": claude_hooks.guard_bash,
    "session-check": claude_hooks.session_check,
}
_EXPECTED = (contract.MissingVariables, hardening.Refused, session_setup.SetupError, GitError)
"""What a command raises to stop with a message, rather than a traceback."""


def _ran(command: Callable[[], None]) -> int:
    """Exit code 0 for a command that raises to fail."""
    command()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_runtime", description="Runs inside a foundry sandbox.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, (func, help_text) in COMMANDS.items():
        subparsers.add_parser(name, help=help_text).set_defaults(func=func)
    hook = subparsers.add_parser("hook", help="a Claude Code hook, as managed settings run it")
    hook.add_argument("name", choices=CLAUDE_HOOKS)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    """Run one command; returns its exit code. What it raises to stop is printed, not a traceback."""
    args = build_parser().parse_args(argv)
    func: Callable[[], int] = CLAUDE_HOOKS[args.name] if args.command == "hook" else args.func
    try:
        return func()
    except _EXPECTED as error:
        if isinstance(error, (contract.MissingVariables, GitError)):
            # Messages that don't say which command they come from; a hook says its own name.
            command = args.name if args.command == "hook" else args.command
            print(f"agent_runtime {command}: {error}", file=sys.stderr)
        else:
            print(error, file=sys.stderr)
        return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
