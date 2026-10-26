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

from agent_runtime import claude_hooks, contract, git_hooks  # noqa: E402

CLAUDE_HOOKS: dict[str, Callable[[], int]] = {
    "guard-bash": claude_hooks.guard_bash,
    "session-check": claude_hooks.session_check,
}

GIT_HOOKS: dict[str, Callable[[Sequence[str]], None]] = {
    "pre-commit": lambda args: git_hooks.pre_commit(),
    "prepare-commit-msg": git_hooks.prepare_commit_msg,
    "pre-push": lambda args: git_hooks.pre_push(),
}
"""The kit's hooks/ stubs call git_hooks directly; these are the same hooks, for running by hand."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_runtime", description="Runs inside a foundry sandbox.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    hook = subparsers.add_parser("hook", help="a Claude Code hook, as managed settings run it")
    hook.add_argument("name", choices=CLAUDE_HOOKS)
    hook.set_defaults(func=lambda args: CLAUDE_HOOKS[args.name]())

    git_hook = subparsers.add_parser("git-hook", help="a git hook, with the arguments git passes it")
    git_hook.add_argument("name", choices=GIT_HOOKS)
    git_hook.add_argument("args", nargs="*")
    git_hook.set_defaults(func=_run_git_hook)
    return parser


def _run_git_hook(args: argparse.Namespace) -> int:
    GIT_HOOKS[args.name](args.args)
    return 0


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
