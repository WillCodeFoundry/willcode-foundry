from pathlib import Path

import pytest

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.launch import Launch, ensure_paths_safe, prepare
from foundry.agent_sandbox.sbx import Sbx
from foundry.agent_sandbox.ssh_agent import SshAgent

FP = "256 SHA256:abc comment (ED25519)"


class Responses(dict):  # type: ignore[type-arg]
    """FakeHost responses that also accept any `sh -c` known_hosts script."""

    def __init__(self, sdir: Path, base: dict) -> None:  # type: ignore[type-arg]
        super().__init__(base)
        self._sh = ("sbx", "env", "exec", str(sdir), "--", "sh", "-c")

    def __missing__(self, key):  # type: ignore[no-untyped-def]
        if key[:7] == self._sh:
            return ""
        raise KeyError(key)


def setup(tmp_path: Path, host):  # type: ignore[no-untyped-def]
    kit = tmp_path / "kit"
    kit.mkdir()
    key = tmp_path / "key"
    key.write_text("k")
    sdir = tmp_path / "s"
    sdir.mkdir()
    (sdir / "sbxenv.yaml").write_text("name: n\n")
    sock = tmp_path / "n.sock"
    agent = SshAgent(host, sock)
    sbx = Sbx(host, Sbx.process_env({}, sock), "n", sdir)
    return kit, key, sdir, sock, agent, sbx


def common(key: Path, sdir: Path) -> dict:  # type: ignore[type-arg]
    e = ("sbx", "env", "exec", str(sdir), "--")
    return {
        ("ssh-add", "-D"): "",
        ("ssh-add", "-q", str(key)): "",
        ("sbx", "policy", "allow", "network", "--sandbox", "n", "github.com:22"): "",
        ("sbx", "secret", "rm", "github", "--sandbox", "n", "-f"): "",
        (*e, "ssh-add", "-l"): FP,
    }


def test_paths_safe_rejects_key_or_envfile_inside_context(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    with pytest.raises(SandboxError, match="inside the context"):
        ensure_paths_safe(kit, kit / "key", tmp_path / "s")
    with pytest.raises(SandboxError, match="inside the context"):
        ensure_paths_safe(kit, tmp_path / "key", kit / "s")
    with pytest.raises(SandboxError, match="contains ':'"):
        ensure_paths_safe(tmp_path / "a:b", tmp_path / "key", tmp_path / "s")
    ensure_paths_safe(kit, tmp_path / "key", tmp_path / "s")


def test_prepare_creates_then_runs_init_after_the_key_check(tmp_path: Path, host) -> None:  # type: ignore[no-untyped-def]
    kit, key, sdir, sock, agent, sbx = setup(tmp_path, host)
    e = ("sbx", "env", "exec", str(sdir), "--")
    host.responses = Responses(sdir, {
        **common(key, sdir),
        ("ssh-add", "-l"): [2, 0, FP],  # no agent; started; listing
        ("ssh-agent", "-a", str(sock), "-s"): "",
        (*e, "true"): [1, 0],  # absent, then present
        ("sbx", "env", "create", "--auto-approve", str(sdir)): "",
        (*e, "/k/bin/session-init"): "",
    })
    prepare(Launch(name="n", env_dir=sdir, context=kit, ssh_key=key, init=("/k/bin/session-init",)), host, agent, sbx)
    cmds = host.commands
    assert ("sbx", "env", "create", "--auto-approve", str(sdir)) in cmds
    assert cmds.index((*e, "/k/bin/session-init")) > cmds.index((*e, "ssh-add", "-l"))


def test_prepare_aborts_when_init_fails(tmp_path: Path, host) -> None:  # type: ignore[no-untyped-def]
    kit, key, sdir, sock, agent, sbx = setup(tmp_path, host)
    e = ("sbx", "env", "exec", str(sdir), "--")
    host.responses = Responses(sdir, {
        **common(key, sdir),
        ("ssh-add", "-l"): [0, FP],
        (*e, "true"): 0,
        (*e, "init"): (1, "boom"),
    })
    with pytest.raises(SandboxError, match="init failed"):
        prepare(Launch(name="n", env_dir=sdir, context=kit, ssh_key=key, init=("init",)), host, agent, sbx)


def test_run_args_auto_approve_and_pass_agent_args(tmp_path: Path, host) -> None:  # type: ignore[no-untyped-def]
    sbx = Sbx(host, {}, "n", tmp_path)
    assert sbx.run_args(()) == ("sbx", "env", "run", "--auto-approve", str(tmp_path))
    assert sbx.run_args(("--continue",))[-2:] == ("--", "--continue")
