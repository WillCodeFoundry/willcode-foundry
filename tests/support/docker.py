"""Containers from the sandbox's template image: the docker tier's helpers."""

import dataclasses
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

from agent_runtime.agent_kit import AgentKit

IMAGE = "docker/sandbox-templates:claude-code-docker"
"""Followed by tag, not pinned, as sbx follows it."""
AGENT_HOME = "/home/agent"
DOCKER_SOCKET = "/var/run/docker.sock"
DOCKER_GROUP = 4242
"""The gid the socket starts in: not a group the template's agent user is in, so only --group-add grants it."""


def docker(*args: str, input: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], input=input, capture_output=True, text=True, check=False)


PULL_ATTEMPTS = 3


def pull(image: str) -> subprocess.CompletedProcess[str]:
    """`docker pull`, tried again after a pause when it fails: CI pulls from Docker Hub anonymously, where a rate
    limit or a dropped connection would otherwise fail a required check for a reason unrelated to the change."""
    pulled = docker("pull", "--quiet", image)
    for attempt in range(1, PULL_ATTEMPTS):
        if pulled.returncode == 0:
            break
        time.sleep(10 * attempt)
        pulled = docker("pull", "--quiet", image)
    return pulled


def repo_digest(image: str) -> str:
    """The digest of the image pulled at this tag: `docker image inspect` gives "<repository>@sha256:…"."""
    inspected = docker("image", "inspect", "--format", "{{index .RepoDigests 0}}", image)
    assert inspected.returncode == 0, inspected.stderr
    return inspected.stdout.strip().partition("@")[2]


@dataclasses.dataclass(frozen=True)
class Container:
    name: str
    agent_kit: Path

    def run(self, user: str, *command: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """``command`` in the container, as ``user``, with ``env`` added to the image's environment."""
        options = [f"--env={name}={value}" for name, value in (env or {}).items()]
        return docker("exec", f"--user={user}", *options, self.name, *command)

    def shell(self, user: str, script: str) -> subprocess.CompletedProcess[str]:
        return self.run(user, "sh", "-c", script)

    def session_init(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        """What the launcher runs, as the agent: the runtime's session-init from the mounted kit."""
        return self.run("agent", *AgentKit(self.agent_kit).command("session-init"), env=env)


def copy_origin(container: Container, origin: Path) -> str:
    """Copy the origin in, owned by the agent, so git trusts it; returns its URL inside the container."""
    inside = f"{AGENT_HOME}/origin.git"
    copied = docker("cp", str(origin), f"{container.name}:{inside}")
    assert copied.returncode == 0, copied.stderr
    owned = container.run("root", "chown", "-R", "agent:agent", inside)
    assert owned.returncode == 0, owned.stderr
    return f"file://{inside}"


def last_line(output: str) -> str:
    lines: Sequence[str] = output.strip().splitlines()
    return lines[-1] if lines else ""
