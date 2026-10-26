"""agent_runtime.claude_hooks: guard-bash against the commands it must allow and refuse, called directly.

session-check needs real checkouts, so it is tested end to end, in tests/agent_kit/test_git_hooks.py.
"""

import io
import json

import pytest

from agent_runtime import claude_hooks


def guard(command: str) -> tuple[int, str]:
    stderr = io.StringIO()
    call = {"tool_name": "Bash", "tool_input": {"command": command}}
    returncode = claude_hooks.guard_bash(io.StringIO(json.dumps(call)), stderr)
    return returncode, stderr.getvalue()


ALLOWED = [
    'git commit -m "feat(cli): add run"',
    'git commit -m "mention --no-verify in a message is fine"',  # a quoted word is one word
    'git commit -am "--no-verify is gone"',
    "git commit --amend --no-edit",
    "git push -u origin task/T1",
    "git pull --rebase origin agent-notes",
    "pytest tests/hooks.py",
    "cat agent-kit/hooks/pre-commit",
    "GIT_TRACE=1 git status",
    # Allowed on purpose: the project's GitHub rulesets refuse force-pushes,
    # deletions and pushes outside task/** and agent-notes, and a local
    # rewrite of unpushed work is harmless.
    "git push --force origin task/T1",
    "git push origin --delete other",
    "git rebase main",
    "git reset --hard HEAD~1",
    "git filter-repo --path x",
]

REFUSED = [
    ("git commit --no-verify -m x", "bypassed"),
    ("git push --no-verify", "bypassed"),
    ("cd repo && git commit --no-verify -m x", "bypassed"),
    ("git -c core.hooksPath=/tmp/h commit -m x", "hook configuration"),
    ("git config core.HOOKSPATH /tmp/h", "hook configuration"),
    ("GIT_CONFIG_PARAMETERS=\"'core.hooksPath'='/tmp'\" git commit -m x", "hook configuration"),
    ("echo 'unbalanced", "could not be parsed"),
]

# Accepted misses, listed in refusal_reason's docstring: simple beats complete for a guardrail.
MISSED_ON_PURPOSE = [
    ("git commit -n -m x", 0),
    ("git commit --no-ver -m x", 0),
    ('sh -c "git commit --no-verify -m x"', 0),
    ("git config --get core.hooksPath", 2),  # only reads, but refused
]


@pytest.mark.parametrize(("command", "returncode"), MISSED_ON_PURPOSE)
def test_accepted_misses(command: str, returncode: int) -> None:
    assert guard(command)[0] == returncode


@pytest.mark.parametrize("command", ALLOWED)
def test_allowed(command: str) -> None:
    returncode, stderr = guard(command)
    assert returncode == 0, stderr


@pytest.mark.parametrize(("command", "reason"), REFUSED)
def test_refused_with_a_reason(command: str, reason: str) -> None:
    returncode, stderr = guard(command)
    assert returncode == 2
    assert reason in stderr
    assert f"Command: {command}" in stderr
    assert "Blockers" in stderr  # says what to do instead


@pytest.mark.parametrize("raw_input", ["not json", "[]", '{"tool_input": "x"}', '{"tool_input": {"command": 3}}'])
def test_input_it_does_not_understand_is_let_through(raw_input: str) -> None:
    assert claude_hooks.guard_bash(io.StringIO(raw_input), io.StringIO()) == 0
