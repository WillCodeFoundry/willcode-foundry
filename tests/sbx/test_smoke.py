"""A real sbx sandbox, launched up to but not including attaching the agent: run by hand, with -m sbx.

It shows what no fake can: that sbx accepts our definition, mounts the kit read-only at its host path, runs
session-init as the agent with sudo the first time, and that the sandbox's private dockerd keeps its socket
root's after a restart. Run it after upgrading sbx, and before merging changes to agent-kit/, src/agent_runtime/
or src/foundry/agent_sandbox/: see "Testing against real sbx" in CONTRIBUTING.md.

It uses this foundry's project foundry-test, role dev and task sbx-0001, and touches only that sandbox and its
session directory: removed before it starts and after it ends, whatever the outcome. The tests run in order,
each building on the one before.
"""

import json
import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from agent_runtime.agent_kit import AgentKit
from foundry import agent_sandbox, config, paths
from foundry.agent_sandbox import SandboxDefinition
from foundry.agent_sandbox.host import SystemHost
from foundry.agent_sandbox.launcher import LaunchRequest, provision_sandbox
from foundry.agent_sandbox.sandbox import SbxCli
from foundry.agent_sandbox.ssh_agent import SshAgentRegistry, ssh_agent_socket_path
from foundry.errors import FoundryError
from foundry.runtime_build import build_runtime
from foundry.session import open_or_create
from foundry.task import Task

pytestmark = pytest.mark.sbx

PROJECT, ROLE, TASK = "foundry-test", "dev", Task.as_open("sbx-0001")
SETTINGS = "/etc/claude-code/managed-settings.json"
DOCKER_SOCKET = "/var/run/docker.sock"


def missing_prerequisites(foundry_root: Path) -> list[str]:
    """Everything the smoke test needs that this machine lacks, all at once."""
    missing = []
    if shutil.which("sbx") is None:
        missing.append("sbx is not on PATH")  # and so `sbx ls` can't say whether you're signed in
    else:
        listed = subprocess.run(["sbx", "ls", "--json"], capture_output=True, text=True, check=False)
        if listed.returncode != 0:
            missing.append(f"`sbx ls --json` failed; sign in with `sbx login`: {listed.stderr.strip()}")
    try:
        foundry_config = config.load(foundry_root)
        project, role = foundry_config.project(PROJECT), foundry_config.role(ROLE)
    except FoundryError as error:
        return [*missing, f"config/foundry.yaml: {error}"]
    if not role.ssh_key_path.is_file():
        missing.append(f"{ROLE}'s ssh key {role.ssh_key_path} is missing")
    remote = subprocess.run(
        ["git", "ls-remote", project.url, f"refs/heads/{TASK.branch}"], capture_output=True, text=True, check=False
    )
    if remote.returncode != 0:
        missing.append(f"can't reach {project.url} to look for {TASK.branch}: {remote.stderr.strip()}")
    elif not remote.stdout.strip():
        missing.append(
            f"{TASK.branch} isn't on {project.url}; create the task once with "
            f"`uv run foundry task create {PROJECT} {TASK.id}`"
        )
    return missing


@dataclass
class Smoke:
    """The smoke sandbox across the tests: what the last launch asked for, and the sandbox it provisioned."""

    foundry_root: Path
    request: LaunchRequest | None = None
    definition: SandboxDefinition | None = None
    sandbox: SbxCli | None = None
    init_output: str = ""
    """What session-init printed at the last launch."""

    def make_launch_request(self) -> LaunchRequest:
        """The session, created if missing, and the runtime built into the kit, as foundry run does: no sbx call yet."""
        foundry_config = config.load(self.foundry_root)
        session = open_or_create(
            self.foundry_root, project=foundry_config.project(PROJECT), role=foundry_config.role(ROLE), task=TASK
        )
        build_runtime(paths.agent_kit_dir(self.foundry_root))
        self.request = session.launch_request()
        return self.request

    def provision_sandbox(self) -> None:
        """The launch up to the agent, with the real host, ssh-agent and sbx client, built as launch builds them."""
        request = self.make_launch_request()
        self.definition = SandboxDefinition.read(request.definition_dir)
        host = SystemHost()
        ssh_agent = SshAgentRegistry(host, uid=os.getuid()).ssh_agent(self.definition.name)
        self.sandbox = SbxCli(
            host,
            sandbox_name=self.definition.name,
            definition_dir=request.definition_dir,
            ssh_agent_socket_path=ssh_agent.socket_path,
        )
        self.init_output = provision_sandbox(request, self.definition, ssh_agent, self.sandbox)

    @property
    def ssh_agent_socket(self) -> Path:
        """Where this sandbox's ssh-agent listens, known before it starts."""
        assert self.request is not None
        return ssh_agent_socket_path(SandboxDefinition.read(self.request.definition_dir).name)

    def run(self, *command: str) -> subprocess.CompletedProcess[str]:
        """``command`` in the sandbox, as the agent, through sbx env exec."""
        assert self.sandbox is not None, "the first launch didn't run"
        return self.sandbox.run(command)

    @property
    def agent_kit(self) -> Path:
        assert self.definition is not None, "the first launch didn't run"
        return self.definition.agent_kit_dir


def sbx_sandboxes() -> dict[str, str]:
    """Every sandbox sbx knows, running or stopped, by name, with its status."""
    listed = subprocess.run(["sbx", "ls", "--json"], capture_output=True, text=True, check=True)
    return {sandbox["name"]: sandbox["status"] for sandbox in json.loads(listed.stdout)["sandboxes"]}


def remove_the_smoke_sandbox(session_dir: Path) -> None:
    """As the README says to recreate a sandbox: sbx env rm --force, then delete its session directory.

    sbx is asked to remove the sandbox only when it has one by the definition's name: a session made but
    never launched has none, and sbx would fail on it. When sbx fails to remove one it has, the run fails naming
    the command, and the dir stays: the sandbox can still be removed by its path.
    """
    if not session_dir.exists():
        return
    definition = session_dir / SandboxDefinition.FILE_NAME
    if definition.is_file() and SandboxDefinition.read(session_dir).name in sbx_sandboxes():
        command = ["sbx", "env", "rm", "--force", str(session_dir)]
        removed = subprocess.run(command, capture_output=True, text=True, check=False)
        if removed.returncode != 0:
            pytest.fail(
                f"`{' '.join(command)}` failed, so {session_dir} is left for you to remove:\n{removed.stderr.strip()}",
                pytrace=False,
            )
    shutil.rmtree(session_dir)


@pytest.fixture(scope="module")
def smoke() -> Iterator[Smoke]:
    foundry_root = paths.find_foundry_root()
    if missing := missing_prerequisites(foundry_root):
        pytest.fail("-m sbx needs:\n" + "\n".join(f"  - {line}" for line in missing), pytrace=False)
    smoke = Smoke(foundry_root)
    # The session names the sandbox; a leftover from an earlier run is removed from its dir.
    try:
        definition_dir = smoke.make_launch_request().definition_dir
    except FoundryError as error:
        pytest.fail(f"a leftover session stops the smoke test before it can remove it: {error}", pytrace=False)
    # Read while sbxenv.yaml exists: removing the sandbox deletes it, and the name is the same at every launch.
    ssh_agent_socket = smoke.ssh_agent_socket
    remove_the_smoke_sandbox(definition_dir)
    try:
        yield smoke
    finally:
        try:
            remove_the_smoke_sandbox(definition_dir)
        finally:
            # Its socket was touched minutes ago, which prune spares as a launch in progress; without the
            # socket, prune kills the agent and the dev role's key with it, however far the launch got.
            ssh_agent_socket.unlink(missing_ok=True)
            agent_sandbox.prune()


def test_a_first_launch_hardens_the_sandbox(smoke: Smoke) -> None:
    smoke.provision_sandbox()  # raises unless session-init exited 0

    checked = smoke.run(*AgentKit(smoke.agent_kit).runtime_command("check-hardening"))

    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "check-hardening: hardened" in checked.stdout
    # What only root mode prints: a relaunch of a sandbox left from an earlier run wouldn't.
    assert "harden: managed settings installed" in smoke.init_output


@pytest.mark.parametrize(
    ("what", "script"),
    [
        ("run sudo", "sudo -n true"),
        ("su to root", "su root -c true </dev/null"),
        ("write in the kit", "touch {kit}/created-by-the-agent"),
        ("write Claude's managed settings", f": >> {SETTINGS}"),
        ("replace the hooks' runtime", "ln -sfn /tmp/agents-own.pyz /etc/claude-code/agent_runtime.pyz"),
        ("use the Docker socket", f"test -w {DOCKER_SOCKET}"),
    ],
)
def test_the_agent_cant(smoke: Smoke, what: str, script: str) -> None:
    assert smoke.run("sh", "-c", script.format(kit=smoke.agent_kit)).returncode != 0, what


def test_a_relaunch_only_checks(smoke: Smoke) -> None:
    smoke.provision_sandbox()  # raises unless session-init exited 0

    assert smoke.request is not None
    relaunched = smoke.run(*smoke.request.init_command)

    assert relaunched.returncode == 0, relaunched.stdout + relaunched.stderr
    assert "check-hardening: hardened" in relaunched.stdout
    assert "harden: managed settings installed" not in relaunched.stdout


def test_after_a_restart_the_docker_socket_is_still_roots(smoke: Smoke) -> None:
    """dockerd recreates its socket when the sandbox starts again, in the group daemon.json names."""
    assert smoke.definition is not None
    # sbx env has no stop; the top-level sbx stop takes the sandbox's name, not its definition dir.
    stopped = subprocess.run(["sbx", "stop", smoke.definition.name], capture_output=True, text=True, check=False)
    assert stopped.returncode == 0, stopped.stderr
    assert sandbox_status(smoke) == "stopped"

    smoke.provision_sandbox()  # starts it again

    deadline = time.monotonic() + 60
    while smoke.run("test", "-S", DOCKER_SOCKET).returncode != 0:
        assert time.monotonic() < deadline, f"dockerd didn't recreate {DOCKER_SOCKET} within a minute"
        time.sleep(2)
    assert smoke.run("stat", "-c", "%G", DOCKER_SOCKET).stdout.strip() == "root"
    assert smoke.run("test", "-w", DOCKER_SOCKET).returncode != 0


def sandbox_status(smoke: Smoke) -> str:
    assert smoke.definition is not None
    return str(sbx_sandboxes().get(smoke.definition.name, "absent"))
