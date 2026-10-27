"""Containers from the sandbox's template image, for running session-init as the launcher does.

The image is the one sbx starts Claude Code sandboxes from, by its tag, pulled fresh for each run: as sbx
does for each new sandbox, so the tests check what new sandboxes get. A template change can therefore turn a
pull request red that didn't cause it; the failure says what changed in the image.

Each container runs `sleep infinity` instead of the template's entrypoint, so nothing starts in it but what a
test runs, and is removed afterwards, whatever the outcome. It mounts a copy of the agent kit at the same
absolute path, as sbx does, read-only unless a test says otherwise, with every file in it world-writable: so
only the mount can stop the agent writing it. It has a Docker socket in a group the agent user isn't in, and
that group added by number, as sbx gives agent processes the docker group. Root runs only inside containers.
"""

import dataclasses
import shutil
import stat
import subprocess
import uuid
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import pytest

from agent_runtime import contract
from foundry.session import SessionVariables
from foundry.task import Task
from tests.conftest import TASK

IMAGE = "docker/sandbox-templates:claude-code-docker"
"""Followed by tag, not pinned, as sbx follows it."""
AGENT_HOME = "/home/agent"
DOCKER_SOCKET = "/var/run/docker.sock"
DOCKER_GROUP = 4242
"""The gid the socket starts in: not a group the template's agent user is in, so only --group-add grants it."""


def docker(*args: str, input: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], input=input, capture_output=True, text=True, check=False)


@pytest.fixture(scope="session")
def image() -> str:
    """The template image, pulled at its tag's current version. -m docker asked for it, so a missing Docker
    daemon fails rather than skips."""
    try:
        info = docker("info")
    except FileNotFoundError:
        pytest.fail("-m docker needs Docker: there is no `docker` command on PATH", pytrace=False)
    if info.returncode != 0:
        pytest.fail(f"-m docker needs a Docker daemon: `docker info` failed:\n{info.stderr.strip()}", pytrace=False)
    pulled = docker("pull", "--quiet", IMAGE)
    if pulled.returncode != 0:
        pytest.fail(f"can't pull {IMAGE}:\n{pulled.stderr.strip()}", pytrace=False)
    return IMAGE


@pytest.fixture(scope="session")
def writable_kit(built_kit: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of the built kit with every file and folder in it writable by anyone, links aside."""
    kit = tmp_path_factory.mktemp("writable") / "agent-kit"
    shutil.copytree(built_kit, kit, symlinks=True)
    for path in [kit, *kit.rglob("*")]:
        if not path.is_symlink():
            path.chmod(0o777 if path.is_dir() else stat.S_IMODE(path.stat().st_mode) | 0o666)
    return kit


@dataclasses.dataclass(frozen=True)
class Container:
    name: str
    kit: Path

    def run(self, user: str, *command: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """``command`` in the container, as ``user``, with ``env`` added to the image's environment."""
        options = [f"--env={name}={value}" for name, value in (env or {}).items()]
        return docker("exec", f"--user={user}", *options, self.name, *command)

    def shell(self, user: str, script: str) -> subprocess.CompletedProcess[str]:
        return self.run(user, "sh", "-c", script)

    def session_init(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        """What the launcher runs, as the agent: the runtime's session-init from the mounted kit."""
        return self.run("agent", *contract.command(self.kit, "session-init"), env=env)


@pytest.fixture
def start_container(image: str) -> Iterator[Callable[..., Container]]:
    """Start containers from the image, each removed when the test ends."""
    started: list[str] = []

    def start(kit: Path, *, read_only: bool = True) -> Container:
        name = f"foundry-sandbox-image-{uuid.uuid4().hex[:12]}"
        mount = f"{kit}:{kit}:ro" if read_only else f"{kit}:{kit}"
        started.append(name)
        run = docker(
            "run", "--detach", f"--name={name}", "--entrypoint=sleep",
            f"--group-add={DOCKER_GROUP}", f"--volume={mount}", image, "infinity",
        )  # fmt: skip
        assert run.returncode == 0, run.stderr
        container = Container(name, kit)
        socket = container.shell(
            "root",
            f"python3 -c \"import socket; socket.socket(socket.AF_UNIX).bind('{DOCKER_SOCKET}')\""
            f" && chgrp {DOCKER_GROUP} {DOCKER_SOCKET} && chmod 0660 {DOCKER_SOCKET}",
        )
        assert socket.returncode == 0, socket.stderr
        return container

    yield start
    for name in started:
        docker("rm", "--force", name)


def copy_origin(container: Container, origin: Path) -> str:
    """Copy the origin in, owned by the agent, so git trusts it; returns its URL inside the container."""
    inside = f"{AGENT_HOME}/origin.git"
    copied = docker("cp", str(origin), f"{container.name}:{inside}")
    assert copied.returncode == 0, copied.stderr
    owned = container.run("root", "chown", "-R", "agent:agent", inside)
    assert owned.returncode == 0, owned.stderr
    return f"file://{inside}"


@pytest.fixture
def sandbox_env(session_variables: Callable[[Task], SessionVariables]) -> Callable[[Path, str], dict[str, str]]:
    """The session variables a sandbox for TASK gets, as foundry sets them, pointed at the mounted kit, the
    agent's home and the copied origin."""

    def env(kit: Path, repo_url: str) -> dict[str, str]:
        variables = dataclasses.replace(
            session_variables(TASK), agent_kit_dir=kit, project_dir=f"{AGENT_HOME}/work/p", repo_url=repo_url
        )
        return variables.to_env()

    return env


@pytest.fixture
def sandbox(
    start_container: Callable[..., Container],
    writable_kit: Path,
    created_task: Path,
    sandbox_env: Callable[[Path, str], dict[str, str]],
) -> Callable[..., tuple[Container, dict[str, str]]]:
    """A container ready for its first launch, and the session variables to launch it with."""

    def make(*, read_only: bool = True) -> tuple[Container, dict[str, str]]:
        container = start_container(writable_kit, read_only=read_only)
        return container, sandbox_env(writable_kit, copy_origin(container, created_task))

    return make


def last_line(output: str) -> str:
    lines: Sequence[str] = output.strip().splitlines()
    return lines[-1] if lines else ""
