"""agent-kit/hooks/ and the runtime's git-hook command they run. Each stub execs the runtime through the link
root mode makes, which a host doesn't have: so here the stubs are read, and the command is run directly.
tests/sandbox_image/test_git_hooks.py runs the stubs as written, by real commits and pushes, in a hardened
container. The rules themselves are tested in-process in tests/agent_runtime/test_git_hooks.py."""

import os
import subprocess
from pathlib import Path

import pytest

from agent_runtime import harden
from agent_runtime.__main__ import GIT_HOOKS
from agent_runtime.agent_kit import PYTHON, PYTHON_FLAGS, AgentKit
from tests.support import AGENT_KIT_SOURCE, TASK, git
from tests.support.kit import runtime_command

HOOKS = sorted(AgentKit(AGENT_KIT_SOURCE).hooks.iterdir())


def test_there_is_a_stub_for_each_git_hook_the_runtime_has() -> None:
    assert [hook.name for hook in HOOKS] == sorted(GIT_HOOKS)


@pytest.mark.parametrize("hook", HOOKS, ids=lambda hook: hook.name)
def test_a_stub_execs_the_hardened_runtime_as_its_own_hook(hook: Path) -> None:
    """The interpreter and flags every call into the runtime uses, the runtime through the link root mode makes,
    and git's arguments passed on; git skips a hook it can't execute, without failing."""
    lines = hook.read_text().splitlines()

    assert lines[0] == "#!/bin/sh"
    assert lines[-1] == f'exec {PYTHON} {PYTHON_FLAGS} {harden.SANDBOX.hooks_runtime_link} git-hook {hook.name} "$@"'
    assert os.access(hook, os.X_OK)


def git_hook(
    kit: Path, env: dict[str, str], *args: str, cwd: Path, stdin: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        runtime_command(kit, "git-hook", *args),
        env={**env, "PATH": os.environ["PATH"]},
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_refusal_is_printed_and_stops_git(built_kit, kit_env, tmp_path) -> None:
    pushed = "refs/heads/main 1111 refs/heads/main 0000\n"

    result = git_hook(built_kit, kit_env(TASK), "pre-push", cwd=tmp_path, stdin=pushed)

    assert result.returncode == 1
    assert result.stderr.startswith("pre-push: refusing\n")
    assert "not main." in result.stderr


def test_what_git_passes_reaches_the_hook(built_kit, kit_env, tmp_path) -> None:
    """prepare-commit-msg gets the message file as git passes it, after the hook's name."""
    git(tmp_path, "init", "-q", "-b", TASK.branch)
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("feat: hello\n")

    result = git_hook(built_kit, kit_env(TASK), "prepare-commit-msg", str(message), "message", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert message.read_text() == f"feat: hello\n\nTask: {TASK.id}\n"


def test_an_unknown_hook_is_refused(built_kit, kit_env, tmp_path) -> None:
    result = git_hook(built_kit, kit_env(TASK), "post-checkout", cwd=tmp_path)

    assert result.returncode == 2
    assert "invalid choice: 'post-checkout'" in result.stderr
