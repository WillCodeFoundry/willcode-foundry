"""agent_runtime.git.Git, against a temporary repository: each of its four ways to run git, and its errors."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from agent_runtime.git import Git, GitError
from tests.conftest import git


@pytest.fixture
def repo(tmp_path: Path, git_identity: Path) -> Path:
    """A repository on main, with one commit holding a file with CRLF line endings."""
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    (repo / "crlf.txt").write_bytes(b"one\r\ntwo\r\n")
    git(repo, "add", "crlf.txt")
    git(repo, "commit", "-qm", "init")
    return repo


def test_output_returns_stdout(repo: Path) -> None:
    assert Git(repo).output("config", "--get", "user.name") == "t\n"


def test_output_bytes_keeps_what_git_wrote(repo: Path) -> None:
    assert Git(repo).output_bytes("show", "HEAD:crlf.txt") == b"one\r\ntwo\r\n"


def test_result_lets_the_caller_read_the_exit_code(repo: Path) -> None:
    result = Git(repo).result("config", "--get", "foundry.unset")

    assert (result.returncode, result.stdout) == (1, "")


def test_succeeds_answers_without_printing(repo: Path, capfd: pytest.CaptureFixture[str]) -> None:
    assert Git(repo).succeeds("rev-parse", "--verify", "refs/heads/nope") is False
    assert Git(repo).succeeds("rev-parse", "--verify", "refs/heads/main") is True

    assert capfd.readouterr() == ("", "")


def test_succeeds_can_show_gits_own_output(repo: Path, capfd: pytest.CaptureFixture[str]) -> None:
    assert Git(repo).succeeds("rev-parse", "--verify", "refs/heads/nope", show_output=True) is False

    assert "fatal:" in capfd.readouterr().err


def test_a_failure_names_the_command_as_given_and_gits_message(repo: Path) -> None:
    with pytest.raises(GitError) as raised:
        Git(repo).output("rev-parse", "--verify", "refs/heads/nope")

    assert raised.value.command == ("rev-parse", "--verify", "refs/heads/nope")
    assert str(raised.value) == f"git rev-parse --verify refs/heads/nope failed: {raised.value.stderr.strip()}"
    assert raised.value.stderr.startswith("fatal:")
    assert "-C" not in str(raised.value)


def test_a_folder_is_acted_on_wherever_this_runs(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert Path(Git(repo).output("rev-parse", "--show-toplevel").strip()) == repo


def test_the_environment_given_is_the_one_git_runs_in(repo: Path) -> None:
    env = {**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "foundry.probe", "GIT_CONFIG_VALUE_0": "yes"}

    assert Git(repo, env).output("config", "--get", "foundry.probe") == "yes\n"


@pytest.mark.parametrize(
    "call",
    [
        lambda g: g.output("status"),
        lambda g: g.output_bytes("status"),
        lambda g: g.result("status"),
        lambda g: g.succeeds("status"),
        lambda g: g.succeeds("status", show_output=True),
        lambda g: g.current_branch(),
    ],
    ids=["output", "output_bytes", "result", "succeeds", "succeeds-shown", "current_branch"],
)
def test_a_missing_git_is_named_by_every_method(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, call: Callable[[Git], object]
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    with pytest.raises(GitError, match=r"^git not found in PATH$"):
        call(Git(repo))


def test_the_current_branch_or_detached(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(repo)
    assert Git().current_branch() == "main"

    git(repo, "switch", "-q", "--detach")
    assert Git().current_branch() == "detached"
    assert Git(repo).current_branch() == "detached"
