"""agent-kit/claude/hooks/guard-bash, run as Claude Code runs it: JSON on stdin."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).parents[2] / "agent-kit" / "claude" / "hooks" / "guard-bash"


def guard(command: str) -> subprocess.CompletedProcess[str]:
    call = {"tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run(
        [sys.executable, str(GUARD)], input=json.dumps(call), capture_output=True, text=True, check=False
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
    result = subprocess.run([sys.executable, str(GUARD)], input="not json", capture_output=True, text=True, check=False)
    assert result.returncode == 0
