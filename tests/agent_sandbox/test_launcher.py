"""provision_sandbox and check_checkout_status: what a launch does to the sandbox before and after the agent run,
against a fake sandbox, with a real SshAgent over a fake host.

The sbx command line behind each step is SbxCli's, tested in test_sandbox.py.
"""

import functools
import os
from pathlib import Path
from typing import NamedTuple

import pytest

from foundry.agent_sandbox.definition import SandboxDefinition
from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.launcher import (
    CheckoutStatus,
    LaunchRequest,
    check_checkout_status,
    launch_summary,
    provision_sandbox,
)
from foundry.agent_sandbox.sandbox import Sandbox
from foundry.agent_sandbox.ssh_agent import SshAgent

KEY_FINGERPRINT = "SHA256:abc"
CHECKOUT_STATUS_COMMAND = ("/k/check-unsaved-work",)


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
def ssh_agent(host, layout: Layout) -> SshAgent:
    """An ssh-agent already running, holding the layout's key once loaded: three ssh-add calls, answered."""
    host.responses = {
        ("ssh-add", "-l"): (0, f"256 {KEY_FINGERPRINT} comment (ED25519)"),
        ("ssh-add", "-D"): "",
        ("ssh-add", "-q", str(layout.ssh_key_path)): "",
    }
    return SshAgent(host, layout.ssh_agent_socket_path, os.getuid())


def launch_request(layout: Layout, **request) -> LaunchRequest:
    """A launch request pointing at the layout's definition and key."""
    return LaunchRequest(
        **{
            "definition_dir": layout.definition_dir,
            "ssh_key_path": layout.ssh_key_path,
            "checkout_status_command": CHECKOUT_STATUS_COMMAND,
            **request,
        }
    )


def run_provision_sandbox(layout: Layout, ssh_agent: SshAgent, sandbox: Sandbox, **request) -> str:
    """provision_sandbox() for a launch request pointing at the layout's definition and key."""
    return provision_sandbox(
        launch_request(layout, **request), SandboxDefinition.read(layout.definition_dir), ssh_agent, sandbox
    )


@pytest.fixture
def make_reachable_sandbox(make_sandbox):
    """make_sandbox, for a sandbox the ssh-agent's key reaches, as it should."""
    return functools.partial(make_sandbox, forwarded_key_fingerprints={KEY_FINGERPRINT})


# --- what provision_sandbox does --------------------------------------------------


def test_a_missing_sandbox_is_created_and_given_github_access(layout, ssh_agent, make_reachable_sandbox) -> None:
    sandbox = make_reachable_sandbox()

    run_provision_sandbox(layout, ssh_agent, sandbox)

    assert sandbox.created
    assert sandbox.has_github_ssh_access


def test_an_existing_sandbox_is_reused(layout, ssh_agent, make_reachable_sandbox) -> None:
    sandbox = make_reachable_sandbox(exists=True)

    run_provision_sandbox(layout, ssh_agent, sandbox)

    assert not sandbox.created
    assert sandbox.has_github_ssh_access


def test_the_sandbox_gets_the_token_file_and_a_launch_without_one_takes_it_away(
    layout, ssh_agent, tmp_path, make_reachable_sandbox
) -> None:
    token_file = tmp_path / "dev.token"
    token_file.write_text("t")
    sandbox = make_reachable_sandbox(exists=True)

    run_provision_sandbox(layout, ssh_agent, sandbox, github_token_path=token_file)
    assert sandbox.github_token_file == token_file

    run_provision_sandbox(layout, ssh_agent, sandbox)
    assert sandbox.github_token_file is None


def test_init_runs_once_the_sandbox_sees_the_key(layout, ssh_agent, make_reachable_sandbox) -> None:
    sandbox = make_reachable_sandbox()

    init_output = run_provision_sandbox(layout, ssh_agent, sandbox, init_command=("/k/bin/session-init",))

    assert sandbox.commands_run == [("/k/bin/session-init",)]
    assert init_output == "ran /k/bin/session-init\n"  # returned, for the caller to show or check


@pytest.mark.parametrize(
    ("forwarded_key_fingerprints", "found"),
    [(None, "no ssh-agent"), ({"SHA256:other"}, "keys"), (set(), "keys")],
)
def test_init_never_runs_when_the_sandbox_sees_other_keys(
    layout, ssh_agent, forwarded_key_fingerprints, found, make_sandbox
):
    sandbox = make_sandbox(forwarded_key_fingerprints=forwarded_key_fingerprints)

    with pytest.raises(SandboxError, match=f"the sandbox sees {found}"):
        run_provision_sandbox(layout, ssh_agent, sandbox, init_command=("/k/bin/session-init",))
    assert sandbox.commands_run == []


def test_an_empty_ssh_agent_never_counts_as_the_expected_keys(layout, ssh_agent, host, make_sandbox) -> None:
    # The host's ssh-agent lists no keys after loading, and the sandbox's is empty too:
    # the sets match, but nothing could push.
    host.responses[("ssh-add", "-l")] = [0, 1]  # running; then holding no keys
    sandbox = make_sandbox(forwarded_key_fingerprints=set())

    with pytest.raises(SandboxError, match="holds no keys after loading them"):
        run_provision_sandbox(layout, ssh_agent, sandbox)


def test_provisioning_aborts_when_init_fails(layout, ssh_agent, make_reachable_sandbox) -> None:
    sandbox = make_reachable_sandbox(exit_codes_by_command={("init",): 1})

    with pytest.raises(SandboxError, match=r"init failed \(init\)"):
        run_provision_sandbox(layout, ssh_agent, sandbox, init_command=("init",))


def test_a_running_agent_refuses_the_launch_before_anything_is_given_to_the_sandbox(
    layout, ssh_agent, make_reachable_sandbox
) -> None:
    """AC5: no second agent; the refusal names the sandbox and how to stop the agent."""
    sandbox = make_reachable_sandbox(exists=True, agent_running=True)

    with pytest.raises(SandboxError) as refused:
        run_provision_sandbox(layout, ssh_agent, sandbox, init_command=("/k/bin/session-init",))

    assert str(refused.value) == (
        "an agent is already running in sandbox n, so no second one is started; stop it with `sbx stop fake`"
    )
    assert not sandbox.has_github_ssh_access
    assert sandbox.github_token_file is None
    assert sandbox.commands_run == []


def test_the_sandbox_port_offers_no_way_to_remove_a_sandbox() -> None:
    """The launcher never removes a sandbox; adding a step to the port should be a decision."""
    steps = {name for name in vars(Sandbox) if not name.startswith("_")}
    assert steps == {
        "ensure_running",
        "give_github_ssh_access",
        "set_github_token_file",
        "forwarded_key_fingerprints",
        "run",
        "is_running",
        "is_agent_running",
        "stop_hint",
        "attach",
    }


@pytest.mark.parametrize(("model", "line"), [(None, "the agent default"), ("opus", "opus")])
def test_the_summary_names_the_model(layout: Layout, model: str | None, line: str) -> None:
    request = launch_request(layout, model=model)
    summary = launch_summary(request, SandboxDefinition.read(layout.definition_dir), layout.ssh_agent_socket_path)
    assert summary[-1] == f"model:      {line}"


def test_the_summary_says_where_the_github_token_comes_from(layout: Layout, tmp_path: Path) -> None:
    def github_line(github_token_path: Path | None) -> list[str]:
        request = launch_request(layout, github_token_path=github_token_path)
        summary = launch_summary(request, SandboxDefinition.read(layout.definition_dir), layout.ssh_agent_socket_path)
        return [line for line in summary if line.startswith("github:")]

    assert github_line(tmp_path / "token") == [f"github:     token from {tmp_path / 'token'}"]
    assert github_line(None) == ["github:     no token"]


# --- layouts provision_sandbox refuses, before touching anything --------------------


def test_a_secret_inside_the_agent_kit_is_refused(layout, ssh_agent, make_sandbox) -> None:
    (layout.agent_kit_dir / "key").write_text("k")
    with pytest.raises(SandboxError, match="inside the agent kit, readable by the sandbox"):
        run_provision_sandbox(layout, ssh_agent, make_sandbox(), ssh_key_path=layout.agent_kit_dir / "key")


def test_a_token_file_inside_the_agent_kit_is_refused(layout, ssh_agent, make_sandbox) -> None:
    (layout.agent_kit_dir / "token").write_text("t")
    with pytest.raises(SandboxError, match="inside the agent kit, readable by the sandbox"):
        run_provision_sandbox(layout, ssh_agent, make_sandbox(), github_token_path=layout.agent_kit_dir / "token")


def test_a_definition_inside_the_agent_kit_is_refused(layout, ssh_agent, tmp_path, make_sandbox) -> None:
    inside = layout.agent_kit_dir / "s"
    inside.mkdir()
    definition = SandboxDefinition(
        name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=layout.agent_kit_dir, variables={}
    )
    definition.write(inside)
    with pytest.raises(SandboxError, match="the sandbox could rewrite it"):
        run_provision_sandbox(layout._replace(definition_dir=inside), ssh_agent, make_sandbox())


def test_an_agent_kit_path_with_a_colon_is_refused(layout, ssh_agent, tmp_path, make_sandbox) -> None:
    colon_kit = tmp_path / "a:b"
    colon_kit.mkdir()
    definition = SandboxDefinition(name="n", workspace_dir=tmp_path / "ws", agent_kit_dir=colon_kit, variables={})
    definition.write(layout.definition_dir)
    with pytest.raises(SandboxError, match="contains ':'"):
        run_provision_sandbox(layout, ssh_agent, make_sandbox())


def test_a_missing_ssh_key_is_refused(layout, ssh_agent, tmp_path, make_sandbox) -> None:
    with pytest.raises(SandboxError, match=r"ssh key '.*' is not a file"):
        run_provision_sandbox(layout, ssh_agent, make_sandbox(), ssh_key_path=tmp_path / "missing")


def test_a_session_whose_workspace_is_gone_is_refused(layout, ssh_agent, tmp_path, make_sandbox) -> None:
    # A session from before the workspace moved into it, its /tmp workspace since cleared.
    (tmp_path / "ws").rmdir()
    sandbox = make_sandbox()
    with pytest.raises(SandboxError, match=r"workspace '.*ws' is not a directory"):
        run_provision_sandbox(layout, ssh_agent, sandbox)
    assert not sandbox.created


# --- check_checkout_status --------------------------------------------------------


def test_a_stopped_sandbox_is_can_t_tell_and_is_not_started_to_check(layout, make_sandbox) -> None:
    sandbox = make_sandbox(exists=True, running=False)

    status = check_checkout_status(launch_request(layout), sandbox)

    assert status == CheckoutStatus(text="can't tell: sandbox n is not running", exit_code=1)
    assert sandbox.commands_run == []  # running anything in it would start it
    assert not sandbox.running


def test_an_agent_still_running_is_can_t_tell_with_how_to_stop_it(layout, make_sandbox) -> None:
    sandbox = make_sandbox(exists=True, agent_running=True)

    status = check_checkout_status(launch_request(layout), sandbox)

    assert status == CheckoutStatus(
        text="can't tell: an agent is still running in sandbox n; stop it with `sbx stop fake`", exit_code=1
    )
    assert sandbox.commands_run == []


def test_a_check_that_fails_is_can_t_tell_with_its_error(layout, make_sandbox) -> None:
    class SbxLsFails(make_sandbox):  # type: ignore[misc]
        def is_running(self) -> bool:
            raise SandboxError("sbx ls failed: daemon not running")

    status = check_checkout_status(launch_request(layout), SbxLsFails(exists=True))

    assert status == CheckoutStatus(text="can't tell: sbx ls failed: daemon not running", exit_code=1)


def test_both_saved_is_the_command_s_output_and_exit_0(layout, make_sandbox) -> None:
    sandbox = make_sandbox(exists=True)

    status = check_checkout_status(launch_request(layout), sandbox)

    assert status == CheckoutStatus(text="ran /k/check-unsaved-work", exit_code=0)
    assert sandbox.commands_run == [CHECKOUT_STATUS_COMMAND]


@pytest.mark.parametrize("command_exit_code", [1, 2])
def test_any_other_exit_is_exit_1_with_the_command_s_stdout_then_stderr(
    layout, make_sandbox, command_exit_code: int
) -> None:
    """1 is unsaved work; anything else is the command failing, which shows its own error."""
    sandbox = make_sandbox(
        exists=True,
        exit_codes_by_command={CHECKOUT_STATUS_COMMAND: command_exit_code},
        stderr_by_command={CHECKOUT_STATUS_COMMAND: "Traceback: boom\n"},
    )

    status = check_checkout_status(launch_request(layout), sandbox)

    assert status == CheckoutStatus(text="ran /k/check-unsaved-work\nTraceback: boom", exit_code=1)
