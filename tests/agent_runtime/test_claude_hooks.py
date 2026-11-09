"""The Claude hooks, in-process, through agent_runtime.commands.claude_hook: guard-bash against the commands it
must allow and refuse, and session-check against real checkouts that session_setup made.

tests/agent_kit/test_managed_settings.py and test_stop_hook.py run each hook once as the managed settings say.
"""

import io
import json
import shutil
from pathlib import Path

import pytest

from agent_runtime import contract
from agent_runtime.commands import claude_hook
from tests.support import TASK, ProcessEnvironment, git


def guard(command: str) -> tuple[int, str]:
    stderr = io.StringIO()
    call = {"tool_name": "Bash", "tool_input": {"command": command}}
    returncode = claude_hook.guard_bash(io.StringIO(json.dumps(call)), stderr)
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
    # What shlex can't parse is scanned rather than refused: a heredoc of prose, a comment's apostrophe.
    "cat > f.md <<'EOF'\nWe don't stop\nEOF",
    "cat <<-EOF\n\tit's fine\n\tEOF",
    "ls # it's here",
    "echo 'unbalanced",
]

REFUSED = [
    ("git commit --no-verify -m x", "bypassed"),
    ("git push --no-verify", "bypassed"),
    ("cd repo && git commit --no-verify -m x", "bypassed"),
    ("git -c core.hooksPath=/tmp/h commit -m x", "hook configuration"),
    ("git config core.HOOKSPATH /tmp/h", "hook configuration"),
    ("GIT_CONFIG_PARAMETERS=\"'core.hooksPath'='/tmp'\" git commit -m x", "hook configuration"),
    # Unparsable, so scanned: still refused.
    ("ls # it's here\ngit commit --no-verify -m x", "bypassed"),
    ("echo it's; git -c core.hooksPath=/tmp/h commit -m x", "hook configuration"),
    ("cat <<EOF\nx\nEOF\ngit commit --no-verify -m x", "bypassed"),
    # A # inside a word isn't a comment.
    ("echo a#b; git commit --no-verify -m x", "bypassed"),
    # A heredoc's body can run: fed to a shell, or expanded.
    ("bash <<'EOF'\ngit commit --no-verify -m x\nEOF", "bypassed"),
    ("sh <<EOF\ngit config core.hooksPath /dev/null\nEOF", "hook configuration"),
    ("cat <<EOF\n$(git commit --no-verify)\nEOF", "bypassed"),
    # A << in a comment or in quotes isn't a heredoc, and hides nothing.
    ("ls # <<X\ngit commit --no-verify", "bypassed"),
    ("echo '<<EOF'\ngit commit --no-verify\nEOF", "bypassed"),
    # Quoting inside a word doesn't hide it.
    ("echo it's; git commit --no-ver''ify", "bypassed"),
    ("git commit --no-ver\\ify -m x", "bypassed"),
    ("echo $(git commit --no-verify -m x)", "bypassed"),
]

# Accepted misses, listed in refusal_reason's docstring: simple beats complete for a guardrail.
MISSED_ON_PURPOSE = [
    ("git commit -n -m x", 0),
    ("git commit --no-ver -m x", 0),
    ('sh -c "git commit --no-verify -m x"', 0),
    ("git config --get core.hooksPath", 2),  # only reads, but refused
    # Unparsable text that mentions --no-verify, documentation say, is refused.
    ('cat > notes.md <<"END"\nNever use --no-verify; it\'s against the rules.\nEND', 2),
    ('git commit -m "(--no-verify)"', 2),  # a message that is exactly that, punctuation stripped
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
    assert "When to stop and ask" in stderr  # says what to do instead


@pytest.mark.parametrize("raw_input", ["not json", "[]", '{"tool_input": "x"}', '{"tool_input": {"command": 3}}'])
def test_input_it_does_not_understand_is_let_through(raw_input: str) -> None:
    assert claude_hook.guard_bash(io.StringIO(raw_input), io.StringIO()) == 0


# --- session-check -----------------------------------------------------------

Checkouts = tuple[contract.SessionVariables, Path, Path]


def stop(variables: contract.SessionVariables, raw_input: str = '{"stop_hook_active": false}') -> str:
    """session-check's decision on this stop, as the JSON it prints; empty when the stop goes through."""
    stdout = io.StringIO()
    assert claude_hook.session_check(io.StringIO(raw_input), stdout, variables) == 0
    return stdout.getvalue()


def block_reason(variables: contract.SessionVariables, raw_input: str = '{"stop_hook_active": false}') -> str:
    decision = json.loads(stop(variables, raw_input))
    assert decision["decision"] == "block"
    return str(decision["reason"])


def commit(cwd: Path, name: str, message: str) -> None:
    (cwd / name).parent.mkdir(parents=True, exist_ok=True)
    (cwd / name).write_text(f"{name}\n")
    git(cwd, "add", name)
    git(cwd, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", message)


def test_a_stop_goes_through_when_both_checkouts_are_clean_and_pushed(checkouts: Checkouts) -> None:
    variables, _, _ = checkouts

    assert stop(variables) == ""


def test_a_stop_is_blocked_by_uncommitted_and_unpushed_work(checkouts: Checkouts) -> None:
    variables, code, notes = checkouts
    (code / "wip.txt").write_text("x\n")
    commit(notes, f"{TASK.task_notes_dir}/PROGRESS.md", f"{TASK.id}: progress")

    reason = block_reason(variables)

    assert "code checkout has uncommitted changes; notes checkout has commits not pushed" in reason
    assert reason.endswith('Commit and push that work (see "Git rules" in AGENTS.md), then finish.')


def test_a_stop_is_blocked_by_commits_left_on_the_branch_after_switching_away(checkouts: Checkouts) -> None:
    """The branch is compared with origin, not only HEAD: a detached HEAD at origin's commit hides nothing."""
    variables, code, _ = checkouts
    commit(code, "work.txt", "feat: work")
    git(code, "switch", "-q", "--detach", f"origin/{TASK.branch}")

    assert f"code checkout has commits not pushed to origin/{TASK.branch}" in block_reason(variables)


def test_commits_origin_has_but_the_checkout_hasn_t_fetched_count_as_pushed(checkouts: Checkouts) -> None:
    """Pushed to origin's URL rather than to the remote, so origin/<branch> in the checkout stays behind: the
    check fetches it before comparing."""
    variables, code, _ = checkouts
    commit(code, "work.txt", "feat: work")
    origin_url = git(code, "remote", "get-url", "origin").stdout.strip()
    git(code, "-c", "core.hooksPath=/dev/null", "push", "-q", origin_url, f"HEAD:refs/heads/{TASK.branch}")

    assert stop(variables) == ""


def test_a_stop_is_blocked_when_a_checkout_cant_be_checked(checkouts: Checkouts) -> None:
    """git failing is no evidence that nothing is unsaved."""
    variables, code, _ = checkouts
    shutil.rmtree(code)

    assert f"code checkout can't be checked: `git -C {code} status --porcelain` failed: " in block_reason(variables)


def test_a_stop_is_blocked_when_git_is_missing(
    checkouts: Checkouts, tmp_path: Path, process_environment: ProcessEnvironment
) -> None:
    variables, _, _ = checkouts
    empty = tmp_path / "empty"
    empty.mkdir()
    process_environment.set_env({"PATH": str(empty)})

    assert "code checkout can't be checked: git not found in PATH" in block_reason(variables)


@pytest.mark.parametrize(
    "raw_input", ['{"stop_hook_active": true}', '{"stop_hook_active" : true}', '{\n  "stop_hook_active":\ttrue\n}']
)
def test_a_stop_caused_by_this_hook_blocking_goes_through(checkouts: Checkouts, raw_input: str) -> None:
    """Already looping on this hook: the stop goes through rather than spin, whatever the JSON's spacing."""
    variables, code, _ = checkouts
    (code / "wip.txt").write_text("x\n")

    assert stop(variables, raw_input) == ""


@pytest.mark.parametrize("raw_input", ["not json", "[]", '{"stop_hook_active": "true"}'])
def test_input_that_is_not_the_looping_flag_still_gets_checked(checkouts: Checkouts, raw_input: str) -> None:
    variables, code, _ = checkouts
    (code / "wip.txt").write_text("x\n")

    assert "code checkout has uncommitted changes" in block_reason(variables, raw_input)
