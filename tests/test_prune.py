"""foundry prune: its report, that the command exists, and end to end through cli.main."""

import os
import subprocess
from pathlib import Path

import pytest

from foundry import cli
from foundry.agent_sandbox import Pruned
from foundry.commands.prune import report


def test_each_killed_ssh_agent_is_reported() -> None:
    assert report(Pruned(ssh_agents=["dev-p-a", "dev-p-b"])) == [
        "killed the ssh-agent of dev-p-a",
        "killed the ssh-agent of dev-p-b",
    ]


def test_nothing_to_prune_says_so() -> None:
    assert report(Pruned(ssh_agents=[])) == ["nothing to prune"]


def test_prune_is_a_command() -> None:
    args = cli.build_parser().parse_args(["prune"])
    assert args.func.__module__ == "foundry.commands.prune"


def test_prune_prints_what_it_killed_or_an_error_and_exits_accordingly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, with stand-ins on PATH: sbx lists no live sandbox, and ps lists one process, a sleep
    of the test's own, under the command line of a sandbox's ssh-agent. The real ps would list a developer's
    ssh-agents, for prune to kill."""
    sleeping = subprocess.Popen(["sleep", "60"])
    stand_ins = {
        "sbx": "echo '{\"sandboxes\": []}'",
        "ps": f"echo '{sleeping.pid} ssh-agent -a /tmp/sbx-agents/dev-p-gone.sock -s'",
    }
    for name, script in stand_ins.items():
        (tmp_path / name).write_text(f"#!/bin/sh\n{script}\n")
        (tmp_path / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    try:
        assert cli.main(["prune"]) == 0
        assert capsys.readouterr() == ("killed the ssh-agent of dev-p-gone\n", "")
        assert sleeping.wait(timeout=10) != 0
    finally:
        sleeping.kill()

    (tmp_path / "sbx").write_text("#!/bin/sh\necho 'not logged in' >&2\nexit 1\n")
    assert cli.main(["prune"]) == 1
    assert capsys.readouterr() == ("", "error: sbx ls failed: not logged in\n")
