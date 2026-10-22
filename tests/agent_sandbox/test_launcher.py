from pathlib import Path

import pytest

from foundry.agent_sandbox.definition import SandboxDefinition
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.launcher import LaunchRequest, prepare, require_safe_paths
from foundry.agent_sandbox.sbx import Sbx
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
    SandboxDefinition(name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=kit, variables={}).write(sdir)
    return kit, key, sdir, tmp_path / "n.sock"


def run_prepare(layout, host, **request) -> LaunchRequest:
    """prepare() for a launch request pointing at the layout's definition."""
    _, key, sdir, sock = layout
    launch_request = LaunchRequest(definition_dir=sdir, ssh_key_path=key, **request)
    prepare(launch_request, SandboxDefinition.read(sdir), host, SshAgent(host, sock), Sbx(host, {}, "n", sdir))
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


def test_safe_paths_reject_secrets_or_the_definition_inside_agent_kit(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    with pytest.raises(SandboxError, match="inside the agent kit"):
        require_safe_paths(kit, tmp_path / "s", [kit / "key"])
    with pytest.raises(SandboxError, match="inside the agent kit"):
        require_safe_paths(kit, tmp_path / "s", [tmp_path / "key", kit / "token"])
    with pytest.raises(SandboxError, match="inside the agent kit"):
        require_safe_paths(kit, kit / "s", [tmp_path / "key"])
    with pytest.raises(SandboxError, match="contains ':'"):
        require_safe_paths(tmp_path / "a:b", tmp_path / "s", [])
    require_safe_paths(kit, tmp_path / "s", [tmp_path / "key"])


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


def test_a_failing_token_source_never_reports_the_token(layout, host, tmp_path) -> None:
    _kit, key, sdir, _sock = layout
    token_file = tmp_path / "dev.token"
    token_file.write_text(TOKEN)
    host.responses = responses(key, sdir)
    host.responses[("sbx", "secret", "set", "github", "--sandbox", "n", "--command", f"cat {token_file}")] = 1
    with pytest.raises(SandboxError, match="sbx secret set failed") as error:
        run_prepare(layout, host, github_token_path=token_file)
    assert TOKEN not in str(error.value)
    assert TOKEN not in repr(LaunchRequest(definition_dir=sdir, ssh_key_path=key, github_token_path=token_file))


def test_prepare_aborts_when_init_fails(layout, host) -> None:
    _kit, key, sdir, _sock = layout
    host.responses = responses(key, sdir)
    host.responses[exec_command(sdir, "init")] = (1, "boom")

    with pytest.raises(SandboxError, match="init failed"):
        run_prepare(layout, host, init_command=("init",))


def test_attach_command_auto_approves_and_passes_agent_args(tmp_path: Path, host) -> None:
    sbx = Sbx(host, {}, "n", tmp_path)
    assert sbx.attach_command(()) == ("sbx", "env", "run", "--auto-approve", str(tmp_path))
    assert sbx.attach_command(("--continue",))[-2:] == ("--", "--continue")


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
