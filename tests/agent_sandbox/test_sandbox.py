"""SbxCli: the sbx command line each Sandbox method runs, and what it makes of the result, against a FakeHost;
and list_live_sandboxes."""

from collections import defaultdict
from pathlib import Path

import pytest

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.github_host_keys import GITHUB_HOST_KEYS
from foundry.agent_sandbox.sandbox import SbxCli, list_live_sandboxes

SOCKET = Path("/tmp/sbx-agents/n.sock")
ENV = {"PATH": "/bin", "SSH_AUTH_SOCK": str(SOCKET)}
TOKEN = "ghp_never_in_a_command_line"


@pytest.fixture
def definition_dir(tmp_path: Path) -> Path:
    return tmp_path / "sessions" / "n"


@pytest.fixture
def sbx_cli(host, definition_dir: Path) -> SbxCli:
    host.environ_value = {"PATH": "/bin", "SSH_AUTH_SOCK": "/personal.sock", "SSH_AGENT_PID": "42"}
    return SbxCli(host, sandbox_name="n", definition_dir=definition_dir, ssh_agent_socket_path=SOCKET)


def exec_in(definition_dir: Path, *command: str) -> tuple[str, ...]:
    return ("sbx", "env", "exec", str(definition_dir), "--", *command)


def test_every_call_carries_the_socket_of_the_sandbox_never_the_personal_ssh_agent(
    host, sbx_cli: SbxCli, definition_dir: Path
) -> None:
    host.responses = defaultdict(str)  # every command succeeds
    sbx_cli.ensure_running()
    sbx_cli.give_github_ssh_access()
    assert [env for _, env in host.calls] == [ENV] * len(host.calls)


def create(definition_dir: Path) -> tuple[str, ...]:
    return ("sbx", "env", "create", "--auto-approve", str(definition_dir))


def test_a_sandbox_it_can_reach_is_started_not_created(host, sbx_cli: SbxCli, definition_dir: Path) -> None:
    host.responses = {exec_in(definition_dir, "true"): 0}
    sbx_cli.ensure_running()
    assert host.commands == [exec_in(definition_dir, "true")]


def test_a_sandbox_it_cannot_reach_is_created_from_the_definition_without_attaching(
    host, sbx_cli: SbxCli, definition_dir: Path
) -> None:
    host.responses = {exec_in(definition_dir, "true"): 1, create(definition_dir): ""}
    sbx_cli.ensure_running()
    assert host.commands == [exec_in(definition_dir, "true"), create(definition_dir)]


def test_a_failing_create_is_reported(host, sbx_cli: SbxCli, definition_dir: Path) -> None:
    host.responses = {exec_in(definition_dir, "true"): 1, create(definition_dir): 1}
    with pytest.raises(SandboxError, match="sbx env create failed"):
        sbx_cli.ensure_running()


ALLOW_GITHUB_SSH = ("sbx", "policy", "allow", "network", "--sandbox", "n", "github.com:22")


def test_github_ssh_access_is_the_policy_route_then_githubs_host_keys(
    host, sbx_cli: SbxCli, definition_dir: Path
) -> None:
    host.responses = defaultdict(str)  # whatever the script, it succeeds

    sbx_cli.give_github_ssh_access()

    allow, (*shell, script) = host.commands
    assert allow == ALLOW_GITHUB_SSH
    assert tuple(shell) == exec_in(definition_dir, "sh", "-c")
    assert all(key in script for key in GITHUB_HOST_KEYS)


def test_a_refused_policy_route_is_reported_before_touching_known_hosts(host, sbx_cli: SbxCli) -> None:
    host.responses = {ALLOW_GITHUB_SSH: 1}
    with pytest.raises(SandboxError, match="sbx policy allow failed"):
        sbx_cli.give_github_ssh_access()
    assert host.commands == [ALLOW_GITHUB_SSH]


CLEAR_TOKEN = ("sbx", "secret", "rm", "github", "--sandbox", "n", "-f")


def test_the_token_is_cleared_then_read_from_its_file_by_sbx_never_passed(
    host, sbx_cli: SbxCli, tmp_path: Path
) -> None:
    token_file = tmp_path / "secrets dir" / "dev.token"
    set_token = ("sbx", "secret", "set", "github", "--sandbox", "n", "--command", f"cat '{token_file}'")
    host.responses = {CLEAR_TOKEN: "", set_token: ""}
    sbx_cli.set_github_token_file(token_file)
    assert host.commands == [CLEAR_TOKEN, set_token]


def test_no_token_file_only_clears_the_token(host, sbx_cli: SbxCli) -> None:
    host.responses = {CLEAR_TOKEN: ""}
    sbx_cli.set_github_token_file(None)
    assert host.commands == [CLEAR_TOKEN]


def test_a_failing_token_source_never_reports_the_token(host, sbx_cli: SbxCli, tmp_path: Path) -> None:
    token_file = tmp_path / "dev.token"
    token_file.write_text(TOKEN)
    host.responses = {
        CLEAR_TOKEN: "",
        ("sbx", "secret", "set", "github", "--sandbox", "n", "--command", f"cat {token_file}"): 1,
    }
    with pytest.raises(SandboxError, match="sbx secret set failed") as error:
        sbx_cli.set_github_token_file(token_file)
    assert TOKEN not in str(error.value)


def test_a_failing_clear_is_reported(host, sbx_cli: SbxCli) -> None:
    host.responses = {CLEAR_TOKEN: 1}
    with pytest.raises(SandboxError, match="sbx secret rm failed"):
        sbx_cli.set_github_token_file(None)


@pytest.mark.parametrize(
    ("response", "fingerprints"),
    [("256 SHA256:a k (ED25519)\n", {"SHA256:a"}), (1, set()), (2, None)],
)
def test_the_forwarded_fingerprints_are_listed_inside(
    host, sbx_cli: SbxCli, definition_dir: Path, response, fingerprints
):
    host.responses = {exec_in(definition_dir, "ssh-add", "-l"): response}
    assert sbx_cli.forwarded_key_fingerprints() == fingerprints


def test_an_unexpected_ssh_add_failure_inside_is_reported(host, sbx_cli: SbxCli, definition_dir: Path) -> None:
    host.responses = {exec_in(definition_dir, "ssh-add", "-l"): 3}
    with pytest.raises(SandboxError, match="could not list the sandbox's keys"):
        sbx_cli.forwarded_key_fingerprints()


def test_commands_run_inside_with_the_definitions_variables(host, sbx_cli: SbxCli, definition_dir: Path) -> None:
    host.responses = {exec_in(definition_dir, "/k/bin/session-init"): (0, "ok")}
    assert sbx_cli.run(("/k/bin/session-init",)).stdout == "ok"


def test_attaching_runs_sbx_run_by_name_in_the_terminal_with_the_opening_prompt_and_the_socket_of_the_sandbox(
    host, sbx_cli: SbxCli
):
    sbx_cli.attach(None)

    assert host.terminal_runs == [(("sbx", "run", "--name", "n", "--", "Start your turn, as AGENTS.md says."), ENV)]


def test_attaching_with_a_model_gives_it_to_the_agent_before_the_opening_prompt(host, sbx_cli: SbxCli):
    sbx_cli.attach("opus")

    assert [command for command, _ in host.terminal_runs] == [
        ("sbx", "run", "--name", "n", "--", "--model", "opus", "Start your turn, as AGENTS.md says.")
    ]


# --- is_agent_running, stop_hint ----------------------------------------------


@pytest.mark.parametrize(("pgrep_exit_code", "running"), [(0, True), (1, False)])
def test_an_agent_is_running_when_pgrep_finds_claude_in_the_sandbox(
    host, sbx_cli: SbxCli, definition_dir: Path, pgrep_exit_code: int, running: bool
) -> None:
    host.responses = {exec_in(definition_dir, "pgrep", "-x", "claude"): pgrep_exit_code}

    assert sbx_cli.is_agent_running() is running


def test_a_failing_pgrep_is_reported(host, sbx_cli: SbxCli, definition_dir: Path) -> None:
    host.responses = {exec_in(definition_dir, "pgrep", "-x", "claude"): 2}

    with pytest.raises(SandboxError, match="could not check for a running agent"):
        sbx_cli.is_agent_running()


def test_the_stop_hint_names_sbx_stop_and_the_sandbox(sbx_cli: SbxCli) -> None:
    assert sbx_cli.stop_hint() == "stop it with `sbx stop n`"


# --- list_live_sandboxes ------------------------------------------------------

SBX_LS = ("sbx", "ls", "--json")
SBX_LS_JSON = """{
  "sandboxes": [
    {"name": "dev-p-running", "id": "1", "agent": "claude", "status": "running", "workspaces": []},
    {"name": "dev-p-stopped", "id": "2", "agent": "claude", "status": "stopped", "workspaces": []},
    {"name": "dev-p-starting", "id": "3", "agent": "claude", "status": "starting", "workspaces": []}
  ]
}"""


@pytest.mark.parametrize(
    ("sandbox_name", "running"),
    [("dev-p-running", True), ("dev-p-starting", False), ("dev-p-stopped", False), ("dev-p-absent", False)],
)
def test_a_sandbox_is_running_only_with_sbx_s_status_running(
    host, definition_dir: Path, sandbox_name: str, running: bool
) -> None:
    """ "starting" can't be checked yet; asking sbx ls never starts a sandbox, as reaching one would."""
    host.responses = {SBX_LS: SBX_LS_JSON}
    sbx_cli = SbxCli(host, sandbox_name=sandbox_name, definition_dir=definition_dir, ssh_agent_socket_path=SOCKET)

    assert sbx_cli.is_running() is running
    assert host.commands == [SBX_LS]


def test_live_sandboxes_are_those_sbx_lists_that_are_not_stopped(host) -> None:
    host.responses = {SBX_LS: SBX_LS_JSON}

    assert list_live_sandboxes(host) == {"dev-p-running", "dev-p-starting"}


def test_a_failing_sbx_ls_is_reported(host) -> None:
    host.responses = {SBX_LS: 1}

    with pytest.raises(SandboxError, match="sbx ls failed"):
        list_live_sandboxes(host)


def test_sbx_ls_runs_in_the_host_environment(host) -> None:
    host.environ_value = {"PATH": "/bin", "SSH_AUTH_SOCK": "/personal.sock"}
    host.responses = {SBX_LS: SBX_LS_JSON}

    list_live_sandboxes(host)

    assert host.calls == [(SBX_LS, {"PATH": "/bin", "SSH_AUTH_SOCK": "/personal.sock"})]
