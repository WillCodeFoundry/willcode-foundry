"""Sbx: the sbx command line each method runs, and what it makes of the result, against a FakeHost."""

from collections import defaultdict
from pathlib import Path

import pytest

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.github_keys import GITHUB_HOST_KEYS
from foundry.agent_sandbox.sbx import Sbx

ENV = {"PATH": "/bin", "SSH_AUTH_SOCK": "/tmp/sbx-agents/n.sock"}
TOKEN = "ghp_never_in_a_command_line"


@pytest.fixture
def definition_dir(tmp_path: Path) -> Path:
    return tmp_path / "sessions" / "n"


@pytest.fixture
def sbx(host, definition_dir: Path) -> Sbx:
    return Sbx(host, ENV, "n", definition_dir)


def exec_in(definition_dir: Path, *command: str) -> tuple[str, ...]:
    return ("sbx", "env", "exec", str(definition_dir), "--", *command)


def test_the_process_env_carries_the_sandboxs_socket_and_drops_the_personal_agent() -> None:
    environ = {"PATH": "/bin", "SSH_AUTH_SOCK": "/personal.sock", "SSH_AGENT_PID": "42"}
    assert Sbx.process_env(environ, Path("/tmp/sbx-agents/n.sock")) == ENV


def test_every_call_carries_the_process_env(host, sbx: Sbx, definition_dir: Path) -> None:
    host.responses = {
        exec_in(definition_dir, "true"): 0,
        ("sbx", "policy", "allow", "network", "--sandbox", "n", "github.com:22"): "",
    }
    sbx.start_if_exists()
    sbx.ensure_github_ssh_allowed()
    assert [env for _, env in host.calls] == [ENV, ENV]


@pytest.mark.parametrize(("exit_code", "exists"), [(0, True), (1, False)])
def test_start_if_exists_reaches_the_sandbox(host, sbx: Sbx, definition_dir: Path, exit_code, exists) -> None:
    host.responses = {exec_in(definition_dir, "true"): exit_code}
    assert sbx.start_if_exists() is exists


def test_create_creates_from_the_definition_without_attaching(host, sbx: Sbx, definition_dir: Path) -> None:
    host.responses = {("sbx", "env", "create", "--auto-approve", str(definition_dir)): ""}
    sbx.create()
    assert host.commands == [("sbx", "env", "create", "--auto-approve", str(definition_dir))]


def test_a_failing_create_is_reported(host, sbx: Sbx, definition_dir: Path) -> None:
    host.responses = {("sbx", "env", "create", "--auto-approve", str(definition_dir)): 1}
    with pytest.raises(SandboxError, match="sbx env create failed"):
        sbx.create()


def test_github_ssh_is_allowed_by_policy(host, sbx: Sbx) -> None:
    allow = ("sbx", "policy", "allow", "network", "--sandbox", "n", "github.com:22")
    host.responses = {allow: ""}
    sbx.ensure_github_ssh_allowed()
    assert host.commands == [allow]
    host.responses = {allow: 1}
    with pytest.raises(SandboxError, match="sbx policy allow failed"):
        sbx.ensure_github_ssh_allowed()


def test_githubs_host_keys_are_seeded_into_known_hosts(host, sbx: Sbx, definition_dir: Path) -> None:
    host.responses = defaultdict(str)  # whatever the script, it succeeds

    sbx.ensure_known_hosts()

    ((*shell, script),) = host.commands
    assert tuple(shell) == exec_in(definition_dir, "sh", "-c")
    assert all(key in script for key in GITHUB_HOST_KEYS)


def test_the_token_is_read_from_its_file_by_sbx_never_passed(host, sbx: Sbx, tmp_path: Path) -> None:
    token_file = tmp_path / "secrets dir" / "dev.token"
    set_token = ("sbx", "secret", "set", "github", "--sandbox", "n", "--command", f"cat '{token_file}'")
    host.responses = {set_token: ""}
    sbx.set_github_token_source(token_file)
    assert host.commands == [set_token]


def test_a_failing_token_source_never_reports_the_token(host, sbx: Sbx, tmp_path: Path) -> None:
    token_file = tmp_path / "dev.token"
    token_file.write_text(TOKEN)
    host.responses = {("sbx", "secret", "set", "github", "--sandbox", "n", "--command", f"cat {token_file}"): 1}
    with pytest.raises(SandboxError, match="sbx secret set failed") as error:
        sbx.set_github_token_source(token_file)
    assert TOKEN not in str(error.value)


def test_the_token_is_cleared(host, sbx: Sbx) -> None:
    clear = ("sbx", "secret", "rm", "github", "--sandbox", "n", "-f")
    host.responses = {clear: ""}
    sbx.clear_github_token()
    assert host.commands == [clear]
    host.responses = {clear: 1}
    with pytest.raises(SandboxError, match="sbx secret rm failed"):
        sbx.clear_github_token()


@pytest.mark.parametrize(
    ("response", "fingerprints"),
    [("256 SHA256:a k (ED25519)\n", {"SHA256:a"}), (1, set()), (2, None)],
)
def test_the_forwarded_fingerprints_are_listed_inside(host, sbx: Sbx, definition_dir: Path, response, fingerprints):
    host.responses = {exec_in(definition_dir, "ssh-add", "-l"): response}
    assert sbx.agent_fingerprints() == fingerprints


def test_an_unexpected_ssh_add_failure_inside_is_reported(host, sbx: Sbx, definition_dir: Path) -> None:
    host.responses = {exec_in(definition_dir, "ssh-add", "-l"): 3}
    with pytest.raises(SandboxError, match="could not list the sandbox's keys"):
        sbx.agent_fingerprints()


def test_commands_run_inside_with_the_definitions_variables(host, sbx: Sbx, definition_dir: Path) -> None:
    host.responses = {exec_in(definition_dir, "/k/bin/session-init"): (0, "ok")}
    assert sbx.exec_in_sandbox("/k/bin/session-init").stdout == "ok"


def test_attaching_auto_approves(sbx: Sbx, definition_dir: Path) -> None:
    assert sbx.attach_command() == ("sbx", "env", "run", "--auto-approve", str(definition_dir))
