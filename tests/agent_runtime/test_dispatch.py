"""agent_runtime.__main__.parse: which command a command line names, and what calling it runs."""

from functools import partial

from agent_runtime import claude_hooks, session_setup
from agent_runtime.__main__ import GIT_HOOKS, Invocation, parse


def test_a_command_is_named_as_typed_and_calls_its_function() -> None:
    assert parse(["session-setup"]) == Invocation("session-setup", session_setup.session_setup)


def test_a_claude_hook_is_named_without_its_kind() -> None:
    assert parse(["claude-hook", "guard-bash"]) == Invocation("guard-bash", claude_hooks.guard_bash)


def test_a_git_hook_is_given_what_git_passed_it() -> None:
    invocation = parse(["git-hook", "prepare-commit-msg", "/tmp/message", "message"])

    assert invocation.name == "prepare-commit-msg"
    assert isinstance(invocation.call, partial)
    assert (invocation.call.func, invocation.call.args) == (
        GIT_HOOKS["prepare-commit-msg"],
        (["/tmp/message", "message"],),
    )
