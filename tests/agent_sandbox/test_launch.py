from pathlib import Path

import pytest

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.launch import Launch, ensure_paths_safe, prepare
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
    (sdir / "sbxenv.yaml").write_text("name: n\n")
    return kit, key, sdir, tmp_path / "n.sock"


def exec_in(sdir: Path, *cmd: str) -> tuple[str, ...]:
    return ("sbx", "env", "exec", str(sdir), "--", *cmd)


def responses(key: Path, sdir: Path) -> Responses:
    """The calls every prepare() makes once the agent is up and the sandbox exists."""
    base = {
        ("ssh-add", "-l"): [0, FP],
        ("ssh-add", "-D"): "",
        ("ssh-add", "-q", str(key)): "",
        exec_in(sdir, "true"): 0,
        ("sbx", "policy", "allow", "network", "--sandbox", "n", "github.com:22"): "",
        ("sbx", "secret", "rm", "github", "--sandbox", "n", "-f"): "",
        exec_in(sdir, "ssh-add", "-l"): FP,
    }
    return Responses(sdir, base)


def test_paths_safe_rejects_secrets_or_envfile_inside_context(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    with pytest.raises(SandboxError, match="inside the context"):
        ensure_paths_safe(kit, tmp_path / "s", [kit / "key"])
    with pytest.raises(SandboxError, match="inside the context"):
        ensure_paths_safe(kit, tmp_path / "s", [tmp_path / "key", kit / "token"])
    with pytest.raises(SandboxError, match="inside the context"):
        ensure_paths_safe(kit, kit / "s", [tmp_path / "key"])
    with pytest.raises(SandboxError, match="contains ':'"):
        ensure_paths_safe(tmp_path / "a:b", tmp_path / "s", [])
    ensure_paths_safe(kit, tmp_path / "s", [tmp_path / "key"])


def test_prepare_creates_then_runs_init_after_the_key_check(layout, host) -> None:
    kit, key, sdir, sock = layout
    host.responses = responses(key, sdir)
    host.responses[("ssh-add", "-l")] = [2, 0, FP]  # no agent; started; listing
    host.responses[("ssh-agent", "-a", str(sock), "-s")] = ""
    host.responses[exec_in(sdir, "true")] = [1, 0]  # absent, then present
    host.responses[("sbx", "env", "create", "--auto-approve", str(sdir))] = ""
    host.responses[exec_in(sdir, "/k/bin/session-init")] = ""

    sbx = Sbx(host, {}, "n", sdir)
    prepare(
        Launch(name="n", env_dir=sdir, context=kit, ssh_key=key, init=("/k/bin/session-init",)),
        host,
        SshAgent(host, sock),
        sbx,
    )

    cmds = host.commands
    assert ("sbx", "env", "create", "--auto-approve", str(sdir)) in cmds
    assert cmds.index(exec_in(sdir, "/k/bin/session-init")) > cmds.index(exec_in(sdir, "ssh-add", "-l"))


def test_prepare_fresh_removes_the_existing_sandbox_first(layout, host) -> None:
    kit, key, sdir, sock = layout
    host.responses = responses(key, sdir)
    host.responses[exec_in(sdir, "true")] = [0, 1, 0]  # exists; gone after rm; created
    host.responses[("sbx", "env", "rm", "--auto-approve", str(sdir))] = ""
    host.responses[("sbx", "env", "create", "--auto-approve", str(sdir))] = ""

    prepare(
        Launch(name="n", env_dir=sdir, context=kit, ssh_key=key, fresh=True),
        host,
        SshAgent(host, sock),
        Sbx(host, {}, "n", sdir),
    )

    cmds = host.commands
    assert cmds.index(("sbx", "env", "rm", "--auto-approve", str(sdir))) < cmds.index(
        ("sbx", "env", "create", "--auto-approve", str(sdir))
    )


def test_prepare_gives_sbx_the_token_file_never_the_token(layout, host, tmp_path) -> None:
    kit, key, sdir, sock = layout
    token_file = tmp_path / "secrets dir" / "dev.token"
    token_file.parent.mkdir()
    token_file.write_text(TOKEN)
    set_token = ("sbx", "secret", "set", "github", "--sandbox", "n", "--command", f"cat '{token_file}'")
    host.responses = responses(key, sdir)
    host.responses[set_token] = ""

    prepare(
        Launch(name="n", env_dir=sdir, context=kit, ssh_key=key, github_token_file=token_file),
        host,
        SshAgent(host, sock),
        Sbx(host, {}, "n", sdir),
    )

    cmds = host.commands
    assert cmds.index(("sbx", "secret", "rm", "github", "--sandbox", "n", "-f")) < cmds.index(set_token)
    assert not any(TOKEN in " ".join(cmd) for cmd in cmds)


def test_a_failing_token_source_never_reports_the_token(layout, host, tmp_path) -> None:
    kit, key, sdir, sock = layout
    token_file = tmp_path / "dev.token"
    token_file.write_text(TOKEN)
    host.responses = responses(key, sdir)
    host.responses[("sbx", "secret", "set", "github", "--sandbox", "n", "--command", f"cat {token_file}")] = 1
    launch = Launch(name="n", env_dir=sdir, context=kit, ssh_key=key, github_token_file=token_file)

    with pytest.raises(SandboxError, match="sbx secret set failed") as error:
        prepare(launch, host, SshAgent(host, sock), Sbx(host, {}, "n", sdir))
    assert TOKEN not in str(error.value) and TOKEN not in repr(launch)


def test_prepare_aborts_when_init_fails(layout, host) -> None:
    kit, key, sdir, sock = layout
    host.responses = responses(key, sdir)
    host.responses[exec_in(sdir, "init")] = (1, "boom")

    with pytest.raises(SandboxError, match="init failed"):
        prepare(
            Launch(name="n", env_dir=sdir, context=kit, ssh_key=key, init=("init",)),
            host,
            SshAgent(host, sock),
            Sbx(host, {}, "n", sdir),
        )


def test_run_args_auto_approve_and_pass_agent_args(tmp_path: Path, host) -> None:
    sbx = Sbx(host, {}, "n", tmp_path)
    assert sbx.run_args(()) == ("sbx", "env", "run", "--auto-approve", str(tmp_path))
    assert sbx.run_args(("--continue",))[-2:] == ("--", "--continue")
