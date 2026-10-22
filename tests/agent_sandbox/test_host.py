import os
import sys

import pytest

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.host import SystemHost


@pytest.fixture
def host() -> SystemHost:
    return SystemHost(os.getuid())


# --- run ------------------------------------------------------------------------


def test_run_executes_the_command_and_captures_output(host):
    result = host.run(["echo", "hi"])

    assert result.stdout == "hi\n"


def test_run_translates_a_missing_executable_into_sandboxerror(host):
    with pytest.raises(SandboxError, match="not-a-real-command not found in PATH"):
        host.run(["not-a-real-command"])


def test_run_passes_the_given_env_to_the_child_process(host):
    result = host.run(
        [sys.executable, "-c", "import os; print(os.environ.get('AGENT_SANDBOX_TEST_VALUE', ''), end='')"],
        env={"AGENT_SANDBOX_TEST_VALUE": "hello"},
    )

    assert result.stdout == "hello"


# --- environ ------------------------------------------------------------------


def test_environ_is_the_processs_own_environment(host):
    assert host.environ() is os.environ


# --- ensure_private_dir ------------------------------------------------------


def test_private_dir_is_created_for_the_owner_only(host, tmp_path):
    host.ensure_private_dir(tmp_path / "sockets")

    assert (tmp_path / "sockets").stat().st_mode & 0o777 == 0o700


def test_private_dir_tightens_existing_permissions(host, tmp_path):
    (tmp_path / "sockets").mkdir(mode=0o755)

    host.ensure_private_dir(tmp_path / "sockets")

    assert (tmp_path / "sockets").stat().st_mode & 0o777 == 0o700


def test_private_dir_refuses_a_directory_owned_by_someone_else(tmp_path):
    host = SystemHost(os.getuid() + 1)

    with pytest.raises(SandboxError, match="not a directory owned by you"):
        host.ensure_private_dir(tmp_path / "sockets")


def test_private_dir_symlink_is_refused_and_target_untouched(host, tmp_path):
    target = tmp_path / "elsewhere"
    target.mkdir(mode=0o755)
    (tmp_path / "sockets").symlink_to(target)

    with pytest.raises(SandboxError, match="not a directory owned by you"):
        host.ensure_private_dir(tmp_path / "sockets")
    assert target.stat().st_mode & 0o777 == 0o755


def test_private_dir_that_is_a_file_is_refused(host, tmp_path):
    (tmp_path / "sockets").touch()

    with pytest.raises(SandboxError, match="not a directory owned by you"):
        host.ensure_private_dir(tmp_path / "sockets")


def test_private_dir_that_is_a_dangling_symlink_is_refused(host, tmp_path):
    (tmp_path / "sockets").symlink_to(tmp_path / "missing")

    with pytest.raises(SandboxError, match="not a directory owned by you"):
        host.ensure_private_dir(tmp_path / "sockets")


# --- reset_socket --------------------------------------------------------------


def test_reset_socket_deletes_an_existing_file(host, tmp_path):
    socket = tmp_path / "sockets" / "dev.sock"
    socket.parent.mkdir(mode=0o700)
    socket.touch()

    host.reset_socket(socket)

    assert not socket.exists()


def test_reset_socket_is_a_noop_when_nothing_is_there(host, tmp_path):
    host.reset_socket(tmp_path / "sockets" / "dev.sock")


def test_reset_socket_also_makes_the_parent_dir_private(host, tmp_path):
    socket = tmp_path / "sockets" / "dev.sock"

    host.reset_socket(socket)

    assert socket.parent.stat().st_mode & 0o777 == 0o700


def test_reset_socket_refuses_a_parent_dir_owned_by_someone_else(tmp_path):
    host = SystemHost(os.getuid() + 1)
    socket = tmp_path / "sockets" / "dev.sock"

    with pytest.raises(SandboxError, match="not a directory owned by you"):
        host.reset_socket(socket)


# --- require_dir / require_file ------------------------------------------------


def test_require_dir_accepts_a_directory(host, tmp_path):
    host.require_dir(tmp_path, "workspace")


def test_require_dir_refuses_a_missing_path(host, tmp_path):
    with pytest.raises(SandboxError, match="is not a directory"):
        host.require_dir(tmp_path / "missing", "workspace")


def test_require_file_accepts_a_file(host, tmp_path):
    target = tmp_path / "key"
    target.touch()

    host.require_file(target, "ssh key")


def test_require_file_refuses_a_directory(host, tmp_path):
    with pytest.raises(SandboxError, match="is not a file"):
        host.require_file(tmp_path, "ssh key")
