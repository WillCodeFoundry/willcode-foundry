"""The runtime's command line: ``/usr/bin/python3 -IS agent_runtime.pyz <command>``."""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial

from agent_runtime import (
    claude_hooks,
    contract,
    git_hooks,
    hardening,
    session_init,
    session_setup,
)
from agent_runtime.git import GitError

Command = Callable[[], int | None]
"""Runs one command, and returns its exit code, or None for 0. Most return nothing and raise to fail, as
agent_runtime's docstring says."""

COMMANDS: dict[str, tuple[Command, str]] = {
    "session-init": (session_init.init, "prepare the sandbox: what the launcher runs before the agent"),
    "session-setup": (session_setup.set_up, "the agent user's part of session-init"),
    "harden": (session_init.harden, "as root: harden the sandbox"),
    "check-hardening": (session_init.check_hardening, "as the agent: check the sandbox is hardened"),
}
CLAUDE_HOOKS: dict[str, Command] = {
    "guard-bash": claude_hooks.guard_bash,
    "session-check": claude_hooks.session_check,
}
GIT_HOOKS: dict[str, Callable[[Sequence[str]], None]] = {
    "pre-commit": lambda _hook_args: git_hooks.pre_commit(),
    "prepare-commit-msg": git_hooks.prepare_commit_msg,
    "pre-push": lambda _hook_args: git_hooks.pre_push(),
}
"""What agent-kit/hooks/pre-commit runs, by the name git ran it as, given what git passed the hook. The other two
hooks link to it."""
_EXPECTED_ERRORS = (
    contract.MissingVariables,
    hardening.HardeningRefused,
    session_setup.SetupRefused,
    git_hooks.GitHookRefused,
    GitError,
)
"""What a command raises to stop with a message, rather than a traceback."""


@dataclass(frozen=True)
class Invocation:
    """One command as the command line asked for it."""

    name: str
    """As messages show it: "session-init", "guard-bash", "pre-commit"."""
    call: Command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_runtime", description="Runs inside a foundry sandbox.")
    subparsers = parser.add_subparsers(dest="kind", required=True)
    for name, (_, help_text) in COMMANDS.items():
        subparsers.add_parser(name, help=help_text).set_defaults(name=name)
    claude_hook = subparsers.add_parser("claude-hook", help="a Claude Code hook, as managed settings run it")
    claude_hook.add_argument("name", choices=CLAUDE_HOOKS)
    git_hook = subparsers.add_parser("git-hook", help="a git hook, as agent-kit/hooks/ runs it")
    git_hook.add_argument("name", choices=GIT_HOOKS)
    git_hook.add_argument("hook_args", nargs=argparse.REMAINDER, help="what git passed the hook")
    return parser


def parse(argv: Sequence[str] | None = None) -> Invocation:
    """The command ``argv`` names, ready to call. Exits with argparse's usage message for anything else."""
    args = build_parser().parse_args(argv)
    match args.kind:
        case "claude-hook":
            return Invocation(args.name, CLAUDE_HOOKS[args.name])
        case "git-hook":
            return Invocation(args.name, partial(GIT_HOOKS[args.name], args.hook_args))
        case _:
            return Invocation(args.name, COMMANDS[args.name][0])


def run(argv: Sequence[str] | None = None) -> int:
    """Run one command, and return its exit code. What it raises to stop is printed, not a traceback."""
    invocation = parse(argv)
    try:
        exit_code = invocation.call()
    except _EXPECTED_ERRORS as error:
        print(_error_message(invocation.name, error), file=sys.stderr)
        return 1
    return 0 if exit_code is None else exit_code


def _error_message(command_name: str, error: Exception) -> str:
    """The error as the user sees it. Most messages already start with their command's name. The two from shared
    code don't, so they get it here."""
    if isinstance(error, (contract.MissingVariables, GitError)):
        return f"agent_runtime {command_name}: {error}"
    return str(error)


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
