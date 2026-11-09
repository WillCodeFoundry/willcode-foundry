"""foundry prune: its report, and end to end through cli.main."""

import subprocess
from pathlib import Path

import pytest

from foundry import cli
from foundry.agent_sandbox import Remnant, RemnantKind
from foundry.commands.prune import report
from tests.support import ProcessEnvironment
from tests.support.machine import scripted_stand_in


def test_each_pruned_remnant_is_reported_with_its_kind_and_sandbox() -> None:
    pruned = [Remnant("dev-p-a", RemnantKind.SSH_AGENT), Remnant("dev-p-b", RemnantKind.SSH_AGENT)]
    assert report(pruned) == ["pruned the ssh-agent of dev-p-a", "pruned the ssh-agent of dev-p-b"]


def test_nothing_to_prune_says_so() -> None:
    assert report([]) == ["nothing to prune"]


def test_prune_prints_what_it_pruned_or_an_error_and_exits_accordingly(
    tmp_path: Path, process_environment: ProcessEnvironment, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real command, with stand-ins on PATH: sbx lists no live sandbox, and ps lists one process. That
    process is a sleep of the test's own, under the command line of a sandbox's ssh-agent. The real ps would
    list a developer's ssh-agents, for prune to kill."""
    sleeping = subprocess.Popen(["sleep", "60"])
    scripted_stand_in(tmp_path, "sbx", "echo '{\"sandboxes\": []}'")
    scripted_stand_in(tmp_path, "ps", f"echo '{sleeping.pid} ssh-agent -a /tmp/sbx-agents/dev-p-gone.sock -s'")
    process_environment.prepend_to_path(tmp_path)

    try:
        assert cli.main(["prune"]) == 0
        assert capsys.readouterr() == ("pruned the ssh-agent of dev-p-gone\n", "")
        assert sleeping.wait(timeout=10) != 0
    finally:
        sleeping.kill()

    scripted_stand_in(tmp_path, "sbx", "echo 'not logged in' >&2\nexit 1")
    assert cli.main(["prune"]) == 1
    assert capsys.readouterr() == ("", "error: sbx ls failed: not logged in\n")
