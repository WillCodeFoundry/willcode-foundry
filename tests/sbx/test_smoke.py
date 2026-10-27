"""A real sbx sandbox, launched up to but not including attaching the agent: run by hand, with -m sbx.

It shows what no fake can: that sbx accepts our definition, mounts the kit read-only at its host path, runs
session-init as the agent with sudo the first time, and that the sandbox's private dockerd keeps its socket
root's after a restart. Run it after upgrading sbx, and before merging changes to agent-kit/, src/agent_runtime/
or src/foundry/agent_sandbox/: see "Testing against real sbx" in the README.

It uses this foundry's project foundry-test, role dev and task sbx-smoke, and touches only that sandbox and its
session directory: removed before it starts and after it ends, whatever the outcome. The tests run in order,
each building on the one before.
"""

import json
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from agent_runtime import contract
from foundry import agent_sandbox, config, paths
from foundry.agent_sandbox import SandboxDefinition
from foundry.agent_sandbox.launcher import LaunchRequest, Started, start
from foundry.commands.run import prepare_launch
from foundry.errors import FoundryError
from foundry.task import Task

pytestmark = pytest.mark.sbx

PROJECT, ROLE, TASK = "foundry-test", "dev", Task("sbx-smoke")
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
    """The smoke sandbox across the tests: what the last launch asked for and started."""

    foundry_root: Path
    request: LaunchRequest | None = None
    started: Started | None = None

    def launch(self) -> Started:
        """The launch up to the agent: the session, the runtime built into the kit, then start."""
        self.request = prepare_launch(self.foundry_root, project_name=PROJECT, role_name=ROLE, task=TASK)
        self.started = start(self.request)
        return self.started

    def run(self, *command: str) -> subprocess.CompletedProcess[str]:
        """``command`` in the sandbox, as the agent, through sbx env exec."""
        assert self.started is not None, "the first launch didn't run"
        return self.started.sandbox.run(command)

    @property
    def kit(self) -> Path:
        assert self.started is not None, "the first launch didn't run"
        return self.started.definition.agent_kit_dir


def remove_the_smoke_sandbox(session_dir: Path) -> None:
    """As the README says to recreate a sandbox: sbx env rm --force, then delete its session directory.

    The folder goes only after sbx removed the sandbox, or when it holds no definition, so there was nothing to
    remove. When sbx fails with a definition there, the run fails naming the command, and the folder stays:
    the sandbox can still be removed by its path.
    """
    if not session_dir.exists():
        return
    command = ["sbx", "env", "rm", "--force", str(session_dir)]
    removed = subprocess.run(command, capture_output=True, text=True, check=False)
    if removed.returncode != 0 and (session_dir / SandboxDefinition.FILE_NAME).is_file():
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
    session_dir = paths.session_dir(foundry_root, f"{ROLE}-{PROJECT}-{TASK.id}")
    remove_the_smoke_sandbox(session_dir)
    try:
        yield Smoke(foundry_root)
    finally:
        remove_the_smoke_sandbox(session_dir)
        agent_sandbox.prune()


def test_a_first_launch_hardens_the_sandbox(smoke: Smoke) -> None:
    smoke.launch()  # raises unless session-init exited 0

    verified = smoke.run(*contract.command(smoke.kit, "harden", "--verify"))

    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert "harden --verify: hardened" in verified.stdout


@pytest.mark.parametrize(
    ("what", "script"),
    [
        ("run sudo", "sudo -n true"),
        ("su to root", "su root -c true </dev/null"),
        ("write in the kit", "touch {kit}/created-by-the-agent"),
        ("write Claude's managed settings", f"echo '{{}}' >> {SETTINGS}"),
        ("replace the hooks' runtime", "ln -sfn /tmp/agents-own.pyz /etc/claude-code/agent_runtime.pyz"),
        ("use the Docker socket", f"test -w {DOCKER_SOCKET}"),
    ],
)
def test_the_agent_cant(smoke: Smoke, what: str, script: str) -> None:
    assert smoke.run("sh", "-c", script.format(kit=smoke.kit)).returncode != 0, what


def test_a_relaunch_only_verifies(smoke: Smoke) -> None:
    smoke.launch()  # raises unless session-init exited 0

    assert smoke.request is not None
    relaunched = smoke.run(*smoke.request.init_command)

    assert relaunched.returncode == 0, relaunched.stdout + relaunched.stderr
    assert "harden --verify: hardened" in relaunched.stdout
    assert "harden: managed settings installed" not in relaunched.stdout


def test_after_a_restart_the_docker_socket_is_still_roots(smoke: Smoke) -> None:
    """dockerd recreates its socket when the sandbox starts again, in the group daemon.json names."""
    usage = subprocess.run(["sbx", "env", "--help"], capture_output=True, text=True, check=False)
    assert " stop" in usage.stdout, f"no stop command in `sbx env --help`; update this test:\n{usage.stdout}"
    assert smoke.request is not None
    stopped = subprocess.run(
        ["sbx", "env", "stop", str(smoke.request.definition_dir)], capture_output=True, text=True, check=False
    )
    assert stopped.returncode == 0, stopped.stderr
    assert sandbox_status(smoke) == "stopped"

    smoke.launch()  # starts it again

    deadline = time.monotonic() + 60
    while smoke.run("test", "-S", DOCKER_SOCKET).returncode != 0:
        assert time.monotonic() < deadline, f"dockerd didn't recreate {DOCKER_SOCKET} within a minute"
        time.sleep(2)
    assert smoke.run("stat", "-c", "%G", DOCKER_SOCKET).stdout.strip() == "root"
    assert smoke.run("test", "-w", DOCKER_SOCKET).returncode != 0


def sandbox_status(smoke: Smoke) -> str:
    assert smoke.started is not None
    listed = subprocess.run(["sbx", "ls", "--json"], capture_output=True, text=True, check=True)
    statuses = {sandbox["name"]: sandbox["status"] for sandbox in json.loads(listed.stdout)["sandboxes"]}
    return str(statuses.get(smoke.started.definition.name, "absent"))
