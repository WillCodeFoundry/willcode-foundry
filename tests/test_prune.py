"""foundry prune: its report, and that the command exists."""

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
