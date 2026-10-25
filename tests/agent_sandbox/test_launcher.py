import os
from pathlib import Path

import pytest

from foundry.agent_sandbox.definition import SandboxDefinition
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.launcher import LaunchRequest, prepare
from foundry.agent_sandbox.sandbox import SbxCli
from foundry.agent_sandbox.ssh_agent import SshAgent

FP = "256 SHA256:abc comment (ED25519)"
TOKEN = "ghp_never_in_a_command_line"


class Responses(dict):  # type: ignore[type-arg]
    """FakeHost responses that also accept any `sh -c` known_hosts script."""

    def __init__(self, sdir: Path, base: dict) -> None:  # type: ignore[type-arg]
        super().__init__(base)
        self._sh = ("sbx", "env", "exec", str(sdir), "--", "sh", "-c")

    def __missing__(self, key):
        if key[:7] == self._sh:
            return ""
        raise KeyError(key)


@pytest.fixture
def layout(tmp_path):
    kit = tmp_path / "kit"
    kit.mkdir()
    key = tmp_path / "key"
    key.write_text("k")
    sdir = tmp_path / "s"
    sdir.mkdir()
    (tmp_path / "ws").mkdir()
    SandboxDefinition(name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=kit, variables={}).write(sdir)
    return kit, key, sdir, tmp_path / "n.sock"


def run_prepare(layout, host, **request) -> LaunchRequest:
    """prepare() for a launch request pointing at the layout's definition."""
    _, key, sdir, sock = layout
    launch_request = LaunchRequest(**{"definition_dir": sdir, "ssh_key_path": key, **request})
    sandbox = SbxCli(host, sandbox_name="n", definition_dir=sdir, ssh_agent_socket_path=sock)
    prepare(launch_request, SandboxDefinition.read(sdir), SshAgent(host, sock, os.getuid()), sandbox)
    return launch_request


def exec_command(sdir: Path, *command: str) -> tuple[str, ...]:
    return ("sbx", "env", "exec", str(sdir), "--", *command)


def responses(key: Path, sdir: Path) -> Responses:
    """The calls every prepare() makes once the agent is up and the sandbox exists."""
    base = {
        ("ssh-add", "-l"): [0, FP],
        ("ssh-add", "-D"): "",
        ("ssh-add", "-q", str(key)): "",
        exec_command(sdir, "true"): 0,
        ("sbx", "policy", "allow", "network", "--sandbox", "n", "github.com:22"): "",
        ("sbx", "secret", "rm", "github", "--sandbox", "n", "-f"): "",
        exec_command(sdir, "ssh-add", "-l"): FP,
    }
    return Responses(sdir, base)


def test_a_secret_inside_the_agent_kit_is_refused(layout, host) -> None:
    kit, _key, _sdir, _sock = layout
    (kit / "key").write_text("k")
    with pytest.raises(SandboxError, match="inside the agent kit, readable by the sandbox"):
        run_prepare(layout, host, ssh_key_path=kit / "key")


def test_a_token_file_inside_the_agent_kit_is_refused(layout, host) -> None:
    kit, _key, _sdir, _sock = layout
    (kit / "token").write_text("t")
    with pytest.raises(SandboxError, match="inside the agent kit, readable by the sandbox"):
        run_prepare(layout, host, github_token_path=kit / "token")


def test_a_definition_inside_the_agent_kit_is_refused(layout, host, tmp_path) -> None:
    kit, key, _sdir, sock = layout
    inside = kit / "s"
    inside.mkdir()
    SandboxDefinition(name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=kit, variables={}).write(inside)
    with pytest.raises(SandboxError, match="the sandbox could rewrite it"):
        run_prepare((kit, key, inside, sock), host)


def test_an_agent_kit_path_with_a_colon_is_refused(layout, host, tmp_path) -> None:
    _kit, _key, sdir, _sock = layout
    colon_kit = tmp_path / "a:b"
    colon_kit.mkdir()
    SandboxDefinition(name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=colon_kit, variables={}).write(sdir)
    with pytest.raises(SandboxError, match="contains ':'"):
        run_prepare(layout, host)


def test_a_missing_ssh_key_is_refused(layout, host, tmp_path) -> None:
    with pytest.raises(SandboxError, match=r"ssh key '.*' is not a file"):
        run_prepare(layout, host, ssh_key_path=tmp_path / "missing")


def test_prepare_creates_then_runs_init_after_the_key_check(layout, host) -> None:
    _kit, key, sdir, sock = layout
    host.responses = responses(key, sdir)
    host.responses[("ssh-add", "-l")] = [2, 0, FP]  # no agent; started; listing
    host.responses[("ssh-agent", "-a", str(sock), "-s")] = ""
    host.responses[exec_command(sdir, "true")] = [1, 0]  # absent, then present
    host.responses[("sbx", "env", "create", "--auto-approve", str(sdir))] = ""
    host.responses[exec_command(sdir, "/k/bin/session-init")] = ""

    run_prepare(layout, host, init_command=("/k/bin/session-init",))

    cmds = host.commands
    assert ("sbx", "env", "create", "--auto-approve", str(sdir)) in cmds
    assert cmds.index(exec_command(sdir, "/k/bin/session-init")) > cmds.index(exec_command(sdir, "ssh-add", "-l"))


def test_prepare_gives_sbx_the_token_file_never_the_token(layout, host, tmp_path) -> None:
    _kit, key, sdir, _sock = layout
    token_file = tmp_path / "secrets dir" / "dev.token"
    token_file.parent.mkdir()
    token_file.write_text(TOKEN)
    set_token = ("sbx", "secret", "set", "github", "--sandbox", "n", "--command", f"cat '{token_file}'")
    host.responses = responses(key, sdir)
    host.responses[set_token] = ""

    run_prepare(layout, host, github_token_path=token_file)

    cmds = host.commands
    assert cmds.index(("sbx", "secret", "rm", "github", "--sandbox", "n", "-f")) < cmds.index(set_token)
    assert not any(TOKEN in " ".join(command) for command in cmds)


def test_prepare_aborts_when_init_fails(layout, host) -> None:
    _kit, key, sdir, _sock = layout
    host.responses = responses(key, sdir)
    host.responses[exec_command(sdir, "init")] = (1, "boom")

    with pytest.raises(SandboxError, match="init failed"):
        run_prepare(layout, host, init_command=("init",))


def test_prepare_never_removes_a_sandbox(layout, host) -> None:
    _kit, key, sdir, _sock = layout
    host.responses = responses(key, sdir)

    run_prepare(layout, host)

    assert not any(command[:3] == ("sbx", "env", "rm") for command in host.commands)


def test_an_empty_agent_never_counts_as_the_expected_keys(layout, host) -> None:
    # The host agent lists no keys after loading, and the sandbox's agent is
    # empty too: the sets match, but nothing could push.
    _kit, key, sdir, _sock = layout
    host.responses = responses(key, sdir)
    host.responses[("ssh-add", "-l")] = [0, 1]  # running; then lists no keys
    host.responses[exec_command(sdir, "ssh-add", "-l")] = 1

    with pytest.raises(SandboxError, match="holds no keys after loading them"):
        run_prepare(layout, host)


def test_a_session_whose_workspace_is_gone_is_refused(layout, host, tmp_path) -> None:
    # A session from before the workspace moved into it, its /tmp workspace since cleared.
    (tmp_path / "ws").rmdir()
    with pytest.raises(SandboxError, match=r"workspace '.*ws' is not a directory"):
        run_prepare(layout, host)
