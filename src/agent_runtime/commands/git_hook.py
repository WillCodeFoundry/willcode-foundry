"""`git-hook`: the git hooks, as agent-kit/hooks/ runs them, in the checkout git is committing or pushing in.

The rules are agent_runtime.git_hooks'. Each function here takes what git passed the hook, and reads the rest from
this process: the session variables, the current directory's repository and, for pre-push, stdin.
"""

import sys
from collections.abc import Sequence

from agent_runtime import contract, git_hooks
from agent_runtime.git import Git


def pre_commit(_hook_args: Sequence[str]) -> None:
    git_hooks.pre_commit(_read_variables("pre-commit"), Git())


def prepare_commit_msg(hook_args: Sequence[str]) -> None:
    git_hooks.prepare_commit_msg(hook_args, _read_variables("prepare-commit-msg"), Git())


def pre_push(_hook_args: Sequence[str]) -> None:
    git_hooks.pre_push(sys.stdin, _read_variables("pre-push"))


def _read_variables(hook: str) -> contract.SessionVariables:
    """The session variables, or a refusal naming the hook and the missing ones."""
    try:
        return contract.read_session_variables()
    except contract.MissingVariables as error:
        raise git_hooks.GitHookRefused(f"{hook}: {error}") from None
