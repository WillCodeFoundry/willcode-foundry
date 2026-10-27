"""session-init, as the launcher runs it, in the sandbox's template image: the first launch and the relaunch,
with real sudo, passwd, /etc, a read-only mount and a numeric docker group, as root inside the container only.

These check, where they matter, what tests/agent_runtime/test_harden.py's modelled machine assumes: what the
agent can write, that a read-only mount stops writes to world-writable files, that regrouping the Docker socket
locks out an agent given the docker group by number, and that /usr/bin/python3 is root's.
"""

from collections.abc import Callable

import pytest

from tests.sandbox_image.conftest import DOCKER_SOCKET, Container, last_line

pytestmark = pytest.mark.docker

SETTINGS = "/etc/claude-code/managed-settings.json"
Sandbox = Callable[..., tuple[Container, dict[str, str]]]


def first_launch(sandbox: Sandbox) -> tuple[Container, dict[str, str]]:
    """A container after a first launch that hardened it."""
    container, env = sandbox()
    launched = container.session_init(env)
    assert launched.returncode == 0, launched.stdout + launched.stderr
    return container, env


def test_the_numeric_docker_group_reaches_the_socket_before_the_first_launch(sandbox: Sandbox) -> None:
    """What hardening has to undo: the agent has the socket's group by number only, and that is enough."""
    container, _ = sandbox()

    assert container.shell("agent", f"test -w {DOCKER_SOCKET}").returncode == 0


def test_a_first_launch_hardens_the_sandbox(sandbox: Sandbox) -> None:
    container, env = sandbox()

    launched = container.session_init(env)

    assert launched.returncode == 0, launched.stdout + launched.stderr
    assert "harden: managed settings installed" in launched.stdout
    assert last_line(launched.stdout) == "harden --verify: hardened"
    installed = container.run("root", "stat", "-c", "%u:%g %a", SETTINGS)
    assert installed.stdout.strip() == "0:0 644"
    kit_copy = container.run("root", "cat", str(container.kit / "claude" / "managed-settings.json")).stdout
    assert container.run("root", "cat", SETTINGS).stdout == kit_copy
    assert container.run("root", "cat", "/etc/docker/daemon.json").stdout.strip() == '{"group": "root"}'


@pytest.mark.parametrize(
    ("what", "script"),
    [
        ("run sudo", "sudo -n true"),
        ("su to root", "su root -c true </dev/null"),
        ("write Claude's managed settings", f"echo '{{}}' >> {SETTINGS}"),
        ("use the Docker socket", f"test -w {DOCKER_SOCKET}"),
    ],
)
def test_after_a_first_launch_the_agent_cant(sandbox: Sandbox, what: str, script: str) -> None:
    container, _ = first_launch(sandbox)

    assert container.shell("agent", script).returncode != 0, what


def test_after_a_first_launch_the_read_only_mount_keeps_the_agent_out_of_the_kit(sandbox: Sandbox) -> None:
    """Every file in the kit is world-writable: only the mount stops the agent."""
    container, _ = first_launch(sandbox)

    created = container.shell("agent", f"touch {container.kit}/created-by-the-agent")

    assert created.returncode != 0
    assert "Read-only file system" in created.stderr


def test_a_relaunch_only_verifies(sandbox: Sandbox) -> None:
    container, env = first_launch(sandbox)

    relaunched = container.session_init(env)

    assert relaunched.returncode == 0, relaunched.stdout + relaunched.stderr
    assert last_line(relaunched.stdout) == "harden --verify: hardened"
    assert "harden: managed settings installed" not in relaunched.stdout  # root mode didn't run


def test_verify_sees_real_permissions(sandbox: Sandbox) -> None:
    container, env = first_launch(sandbox)
    assert container.run("root", "chmod", "0666", SETTINGS).returncode == 0

    relaunched = container.session_init(env)

    assert relaunched.returncode != 0
    assert f"change Claude's managed settings: {SETTINGS} is writable" in relaunched.stderr


def test_the_mount_not_file_modes_protects_the_kit(sandbox: Sandbox) -> None:
    """The same world-writable kit, mounted read-write: verify refuses the first launch."""
    container, env = sandbox(read_only=False)

    launched = container.session_init(env)

    assert launched.returncode != 0
    assert f"change the agent kit: {container.kit} is writable" in launched.stderr
