"""The runtime's command line: ``/usr/bin/python3 -I agent_runtime.pyz <command>``.

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

CLAUDE_HOOKS: dict[str, Callable[[], int]] = {
    "guard-bash": claude_hooks.guard_bash,
    "session-check": claude_hooks.session_check,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_runtime", description="Runs inside a foundry sandbox.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("session-init", help="prepare the sandbox: what the launcher runs before the agent")
    init.set_defaults(func=lambda args: session_init.session_init())
    setup = subparsers.add_parser("session-setup", help="the agent user's part of session-init")
    setup.set_defaults(func=lambda args: session_setup.session_setup())
    hardening = subparsers.add_parser(
        "harden", help="as root: harden the sandbox; with --verify, as the agent: check it is hardened"
    )
    hardening.add_argument("--verify", action="store_true")
    hardening.set_defaults(func=lambda args: session_init.agent_mode() if args.verify else session_init.root_mode())

    hook = subparsers.add_parser("hook", help="a Claude Code hook, as managed settings run it")
    hook.add_argument("name", choices=CLAUDE_HOOKS)
    hook.set_defaults(func=lambda args: CLAUDE_HOOKS[args.name]())

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    """Run one command; returns its exit code. A missing session variable is reported, not raised."""
    args = build_parser().parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.func
    try:
        return handler(args)
    except contract.MissingVariables as error:
        print(f"agent_runtime {args.command}: {error}", file=sys.stderr)
        return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
