"""agent-kit/claude/hooks/guard-bash, run as Claude Code runs it: JSON on stdin."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD_BASH_PATH = Path(__file__).parents[2] / "agent-kit" / "claude" / "hooks" / "guard-bash"


def guard(command: str) -> subprocess.CompletedProcess[str]:
    call = {"tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run(
        [sys.executable, str(GUARD_BASH_PATH)], input=json.dumps(call), capture_output=True, text=True, check=False
    )


ALLOWED = [
    'git commit -m "feat(cli): add run" -m "Task: T1"',
    'git commit -m "mention --no-verify in a message is fine"',  # quoted text is not a flag
    "git commit --amend --no-edit",
    "git commit --signoff -m x",
    "git push -u origin task/T1",
    "git pull --rebase origin agent-notes",
    "git push origin agent-notes && ls -d build",  # -d belongs to ls, not push
    "pytest tests/hooks.py",
    "cat agent-kit/hooks/pre-commit",
    "npm test",
    "git reset HEAD file.txt",
    "GIT_TRACE=1 git status",
    # Values are skipped, so a message or file that looks like an option is not one.
    'git commit -m "-n flag removed"',
    'git commit -am "--no-verify is gone" -m "Task: T1"',
    "git commit -F -n.txt",
    "git commit -mn",  # the message is "n"
    'git push -o "--force" origin task/T1',
    # Reading the hooks path is fine; only changing it is refused.
    "git config --get core.hooksPath",
    "git config core.hooksPath",
    "git config --show-origin --get core.hooksPath",
    "git config get core.hooksPath",
    # Shells with combined flags still run what's checked.
    "bash -lc 'git status'",
    "sh -ec 'pytest -q'",
    "bash -o pipefail -c 'git log | head'",
    "bash script.sh -c",  # a script file, not -c
]

REFUSED = [
    ("git commit --no-verify -m x", "bypassed"),
    ("git commit -nm x", "bypassed"),
    ("git commit -an -m x", "bypassed"),
    ("git push --no-verify", "bypassed"),
    ("git -c core.hooksPath=/tmp/h commit -m x", "hook configuration"),
    ("git config core.HOOKSPATH /tmp/h", "hook configuration"),
    ("GIT_CONFIG_PARAMETERS=\"'core.hooksPath'='/tmp'\" git commit -m x", "hook configuration"),
    ("git push --force origin task/T1", "force-push"),
    ("git push --force-with-lease", "force-push"),
    ("git push -uf origin task/T1", "force-push"),
    ("git push origin +task/T1", "force-push"),
    ("git push --mirror", "force-push"),
    ("git push origin --delete other", "deleting"),
    ("git push origin :other", "deleting"),
    ("git push -d origin other", "deleting"),
    ("git rebase main", "rewriting history"),
    ("git reset --hard HEAD~1", "rewriting history"),
    ("git filter-repo --path x", "rewriting history"),
    ('sh -c "git push --force"', "force-push"),
    ("env FOO=1 git push --force", "force-push"),
    ("echo 'unbalanced", "could not be parsed"),
    # Combined shell flags.
    ('bash -lc "git push -f"', "force-push"),
    ('sh -ec "git push --force origin task/T1"', "force-push"),
    ("bash -xec 'git commit -n -m x'", "bypassed"),
    ("bash -o pipefail -c 'git push -f'", "force-push"),
    ("/bin/bash --login -c 'git rebase main'", "rewriting history"),
    ("GIT_CONFIG_PARAMETERS=\"'core.hooksPath'='/x'\" bash -c 'git commit -m x'", "hook configuration"),
    # Abbreviated long options, which git accepts.
    ("git commit --no-ver -m x", "bypassed"),
    ("git push --no-verif", "bypassed"),
    ("git push --forc origin task/T1", "force-push"),
    ("git push --force-with origin task/T1", "force-push"),
    ("git push --del origin other", "deleting"),
    ("git push --mirr", "force-push"),
    ("git reset --har HEAD~1", "rewriting history"),
    # Changing the hooks path, however it's spelled.
    ("git config --global core.hooksPath /tmp/h", "hook configuration"),
    ("git config --unset core.hooksPath", "hook configuration"),
    ("git config set core.hooksPath /tmp/h", "hook configuration"),
    ("git -c core.hooksPath=/tmp/h config --get user.name", "hook configuration"),
    ("git config --get core.hooksPath && git config core.hooksPath /tmp/h", "hook configuration"),
    # Outside git config, any mention is refused: export would set it for every later git command.
    ("export GIT_CONFIG_PARAMETERS=\"'core.hooksPath'='/x'\"", "hook configuration"),
]


@pytest.mark.parametrize("command", ALLOWED)
def test_allowed(command: str) -> None:
    result = guard(command)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("command", "reason"), REFUSED)
def test_refused_with_a_reason(command: str, reason: str) -> None:
    result = guard(command)
    assert result.returncode == 2
    assert reason in result.stderr
    assert "Blockers" in result.stderr  # says what to do instead


def test_input_it_does_not_understand_is_let_through() -> None:
    result = subprocess.run(
        [sys.executable, str(GUARD_BASH_PATH)], input="not json", capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
