"""agent_runtime.git.Git, against a temporary repository: each of its four ways to run git, and its errors."""

import os
import subprocess
import sys
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


def test_shown_output_comes_after_what_this_process_wrote(repo: Path) -> None:
    """As session-setup's progress reads, with its output a pipe, so block-buffered: its own lines and git's, in
    the order they happened. Run in a process of its own, since pytest's capture buffers differently."""
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    script = (
        "import sys; from pathlib import Path; from agent_runtime.git import Git; "
        "print('before'); Git(Path(sys.argv[1])).succeeds('rev-parse', 'HEAD', show_output=True); print('after')"
    )

    env = {name: value for name, value in os.environ.items() if name != "PYTHONUNBUFFERED"}
    run = subprocess.run([sys.executable, "-c", script, str(repo)], capture_output=True, text=True, env=env, check=True)

    assert run.stdout.splitlines() == ["before", head, "after"]


def test_input_reaches_git(repo: Path) -> None:
    blob = git(repo, "hash-object", "crlf.txt").stdout.strip()

    assert Git(repo).output("hash-object", "--stdin", input="one\r\ntwo\r\n").strip() == blob
    assert Git(repo).succeeds("hash-object", "--stdin", input=b"one\r\ntwo\r\n\xff") is True


def test_output_bytes_raises_on_failure_with_gits_message(repo: Path) -> None:
    with pytest.raises(GitError, match=r"^git show HEAD:absent failed: fatal: "):
        Git(repo).output_bytes("show", "HEAD:absent")


def test_a_failure_names_the_command_as_given_and_gits_message(repo: Path) -> None:
    with pytest.raises(GitError) as raised:
        Git(repo).output("rev-parse", "--verify", "refs/heads/nope")

    assert raised.value.command == ("rev-parse", "--verify", "refs/heads/nope")
    assert str(raised.value) == f"git rev-parse --verify refs/heads/nope failed: {raised.value.stderr.strip()}"
    assert raised.value.stderr.startswith("fatal:")
    assert raised.value.found is True
    assert "-C" not in str(raised.value)


def test_a_failure_quotes_an_argument_with_spaces(repo: Path) -> None:
    with pytest.raises(GitError) as raised:
        Git(repo).output("rev-parse", "--verify", "no such ref")

    assert str(raised.value).startswith("git rev-parse --verify 'no such ref' failed: fatal:")


def test_output_that_isnt_utf_8_is_text_all_the_same(repo: Path) -> None:
    """Text is decoded with replacement characters: output that isn't UTF-8, on success or in git's message,
    never raises UnicodeDecodeError."""
    (repo / "latin-1.txt").write_bytes("café\n".encode("latin-1"))
    git(repo, "add", "latin-1.txt")
    git(repo, "commit", "-qm", "latin-1")

    assert Git(repo).output("show", "HEAD:latin-1.txt") == "caf\ufffd\n"
    with pytest.raises(GitError, match="\ufffd"):
        Git(repo).output("show", "HEAD:caf\udce9")  # a path holding the byte 0xe9, which git's message repeats


def test_a_folder_is_acted_on_wherever_this_runs(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert Path(Git(repo).output("rev-parse", "--show-toplevel").strip()) == repo


PROBE = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "foundry.probe", "GIT_CONFIG_VALUE_0": "yes"}
"""Environment variables that set foundry.probe for git."""


def test_the_environment_given_is_the_one_git_runs_in(repo: Path) -> None:
    assert Git(repo, {**os.environ, **PROBE}).output("config", "--get", "foundry.probe") == "yes\n"


@pytest.mark.parametrize("env", [{}, {"PATH": "/usr/bin:/bin"}], ids=["empty", "PATH only"])
def test_the_environment_given_replaces_this_processs(
    repo: Path, monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    """Nothing of this process's environment reaches git beside it, even with an empty one."""
    for name, value in PROBE.items():
        monkeypatch.setenv(name, value)

    assert Git(repo, env).result("config", "--get", "foundry.probe").returncode == 1


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

    with pytest.raises(GitError, match=r"^git not found in PATH$") as raised:
        call(Git(repo))
    assert raised.value.found is False


def test_the_current_branch_or_detached(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(repo)
    assert Git().current_branch() == "main"

    git(repo, "switch", "-q", "--detach")
    assert Git().current_branch() == "detached"
    assert Git(repo).current_branch() == "detached"
