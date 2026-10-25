"""prepare: what a launch does to the sandbox, against a FakeSandbox, with a real SshAgent over a FakeHost.

The sbx command line behind each step is SbxCli's, tested in test_sandbox.py.
"""

import os
from pathlib import Path
from typing import NamedTuple

import pytest

from foundry.agent_sandbox.definition import SandboxDefinition
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.launcher import LaunchRequest, prepare
from foundry.agent_sandbox.sandbox import Sandbox
from foundry.agent_sandbox.ssh_agent import SshAgent
from tests.agent_sandbox.fakes import FakeHost, FakeSandbox

KEY_FINGERPRINT = "SHA256:abc"


class Layout(NamedTuple):
    agent_kit_dir: Path
    ssh_key_path: Path
    definition_dir: Path
    ssh_agent_socket_path: Path


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    """An agent kit, a key, and a session whose definition points at them."""
    kit = tmp_path / "kit"
    kit.mkdir()
    key = tmp_path / "key"
    key.write_text("k")
    definition_dir = tmp_path / "s"
    definition_dir.mkdir()
    (tmp_path / "ws").mkdir()
    SandboxDefinition(name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=kit, variables={}).write(definition_dir)
    return Layout(kit, key, definition_dir, tmp_path / "sockets" / "n.sock")


@pytest.fixture
def ssh_agent(host: FakeHost, layout: Layout) -> SshAgent:
    """An ssh-agent already running, holding the layout's key once loaded: three ssh-add calls, answered."""
    host.responses = {
        ("ssh-add", "-l"): (0, f"256 {KEY_FINGERPRINT} comment (ED25519)"),
        ("ssh-add", "-D"): "",
        ("ssh-add", "-q", str(layout.ssh_key_path)): "",
    }
    return SshAgent(host, layout.ssh_agent_socket_path, os.getuid())


def run_prepare(layout: Layout, ssh_agent: SshAgent, sandbox: FakeSandbox, **request) -> None:
    """prepare() for a launch request pointing at the layout's definition and key."""
    launch_request = LaunchRequest(
        **{"definition_dir": layout.definition_dir, "ssh_key_path": layout.ssh_key_path, **request}
    )
    prepare(launch_request, SandboxDefinition.read(layout.definition_dir), ssh_agent, sandbox)


def reachable_sandbox(**state) -> FakeSandbox:
    """A sandbox that the ssh-agent's key reaches, as it should."""
    return FakeSandbox(forwarded_key_fingerprints={KEY_FINGERPRINT}, **state)


# --- what prepare does ------------------------------------------------------------


def test_a_missing_sandbox_is_created_and_given_github_access(layout, ssh_agent) -> None:
    sandbox = reachable_sandbox()

    run_prepare(layout, ssh_agent, sandbox)

    assert sandbox.created
    assert sandbox.github_ssh_allowed and sandbox.github_host_keys_trusted


def test_an_existing_sandbox_is_reused(layout, ssh_agent) -> None:
    sandbox = reachable_sandbox(exists=True)

    run_prepare(layout, ssh_agent, sandbox)

    assert not sandbox.created
    assert sandbox.github_ssh_allowed and sandbox.github_host_keys_trusted


def test_the_sandbox_gets_the_token_file_and_a_launch_without_one_takes_it_away(layout, ssh_agent, tmp_path) -> None:
    token_file = tmp_path / "dev.token"
    token_file.write_text("t")
    sandbox = reachable_sandbox(exists=True)

    run_prepare(layout, ssh_agent, sandbox, github_token_path=token_file)
    assert sandbox.github_token_file == token_file

    run_prepare(layout, ssh_agent, sandbox)
    assert sandbox.github_token_file is None


def test_init_runs_once_the_sandbox_sees_the_key(layout, ssh_agent) -> None:
    sandbox = reachable_sandbox()

    run_prepare(layout, ssh_agent, sandbox, init_command=("/k/bin/session-init",))

    assert sandbox.commands_run == [("/k/bin/session-init",)]


@pytest.mark.parametrize(
    ("forwarded_key_fingerprints", "found"),
    [(None, "no ssh-agent"), ({"SHA256:other"}, "keys"), (set(), "keys")],
)
def test_init_never_runs_when_the_sandbox_sees_other_keys(layout, ssh_agent, forwarded_key_fingerprints, found):
    sandbox = FakeSandbox(forwarded_key_fingerprints=forwarded_key_fingerprints)

    with pytest.raises(SandboxError, match=f"the sandbox sees {found}"):
        run_prepare(layout, ssh_agent, sandbox, init_command=("/k/bin/session-init",))
    assert sandbox.commands_run == []


def test_an_empty_ssh_agent_never_counts_as_the_expected_keys(layout, ssh_agent, host) -> None:
    # The host's ssh-agent lists no keys after loading, and the sandbox's is empty too:
    # the sets match, but nothing could push.
    host.responses[("ssh-add", "-l")] = [0, 1]  # running; then holding no keys
    sandbox = FakeSandbox(forwarded_key_fingerprints=set())

    with pytest.raises(SandboxError, match="holds no keys after loading them"):
        run_prepare(layout, ssh_agent, sandbox)


def test_prepare_aborts_when_init_fails(layout, ssh_agent) -> None:
    sandbox = reachable_sandbox(exit_codes_by_command={("init",): 1})

    with pytest.raises(SandboxError, match=r"init failed \(init\)"):
        run_prepare(layout, ssh_agent, sandbox, init_command=("init",))


def test_the_sandbox_port_offers_no_way_to_remove_a_sandbox() -> None:
    """The launcher never removes a sandbox; adding a step to the port should be a decision."""
    steps = {name for name in vars(Sandbox) if not name.startswith("_")}
    assert steps == {
        "start_if_exists",
        "create",
        "allow_github_ssh",
        "trust_github_host_keys",
        "set_github_token_file",
        "forwarded_key_fingerprints",
        "run",
        "attach",
    }


# --- layouts prepare refuses, before touching anything ------------------------------


def test_a_secret_inside_the_agent_kit_is_refused(layout, ssh_agent) -> None:
    (layout.agent_kit_dir / "key").write_text("k")
    with pytest.raises(SandboxError, match="inside the agent kit, readable by the sandbox"):
        run_prepare(layout, ssh_agent, FakeSandbox(), ssh_key_path=layout.agent_kit_dir / "key")


def test_a_token_file_inside_the_agent_kit_is_refused(layout, ssh_agent) -> None:
    (layout.agent_kit_dir / "token").write_text("t")
    with pytest.raises(SandboxError, match="inside the agent kit, readable by the sandbox"):
        run_prepare(layout, ssh_agent, FakeSandbox(), github_token_path=layout.agent_kit_dir / "token")


def test_a_definition_inside_the_agent_kit_is_refused(layout, ssh_agent, tmp_path) -> None:
    inside = layout.agent_kit_dir / "s"
    inside.mkdir()
    definition = SandboxDefinition(
        name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=layout.agent_kit_dir, variables={}
    )
    definition.write(inside)
    with pytest.raises(SandboxError, match="the sandbox could rewrite it"):
        run_prepare(layout._replace(definition_dir=inside), ssh_agent, FakeSandbox())


def test_an_agent_kit_path_with_a_colon_is_refused(layout, ssh_agent, tmp_path) -> None:
    colon_kit = tmp_path / "a:b"
    colon_kit.mkdir()
    definition = SandboxDefinition(name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=colon_kit, variables={})
    definition.write(layout.definition_dir)
    with pytest.raises(SandboxError, match="contains ':'"):
        run_prepare(layout, ssh_agent, FakeSandbox())


def test_a_missing_ssh_key_is_refused(layout, ssh_agent, tmp_path) -> None:
    with pytest.raises(SandboxError, match=r"ssh key '.*' is not a file"):
        run_prepare(layout, ssh_agent, FakeSandbox(), ssh_key_path=tmp_path / "missing")


def test_a_session_whose_workspace_is_gone_is_refused(layout, ssh_agent, tmp_path) -> None:
    # A session from before the workspace moved into it, its /tmp workspace since cleared.
    (tmp_path / "ws").rmdir()
    sandbox = FakeSandbox()
    with pytest.raises(SandboxError, match=r"workspace '.*ws' is not a directory"):
        run_prepare(layout, ssh_agent, sandbox)
    assert not sandbox.created
