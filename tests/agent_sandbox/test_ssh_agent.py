import os
import time
from pathlib import Path

import pytest

from foundry.agent_sandbox.errors import SandboxError
from foundry.agent_sandbox.ssh_agent import SSH_AGENT_SOCKETS_DIR, SshAgent, SshAgentRegistry

LIST = ("ssh-add", "-l")
DELETE_ALL = ("ssh-add", "-D")
NOT_RUNNING, NO_KEYS = 2, 1  # ssh-add -l exit codes
OWN_UID = os.getuid()
PERSONAL_ENV = {"PATH": "/bin", "HOME": "/home/dev", "SSH_AUTH_SOCK": "/personal.sock", "SSH_AGENT_PID": "42"}


@pytest.fixture
def socket(tmp_path):
    return tmp_path / "sockets" / "dev.sock"


@pytest.fixture
def make_agent(host, socket):
    host.environ_value = PERSONAL_ENV
    return lambda uid=OWN_UID: SshAgent(host, socket, uid)


def start(socket):
    return ("ssh-agent", "-a", str(socket), "-s")


# --- environment ------------------------------------------------------------


def test_ssh_add_calls_only_carry_path_and_the_sandboxs_socket(host, make_agent, socket):
    host.responses = {LIST: NO_KEYS}

    make_agent().ensure_running()

    assert host.calls == [(LIST, {"PATH": "/bin", "SSH_AUTH_SOCK": str(socket)})]


# --- ensure_running ---------------------------------------------------------


def test_starts_an_agent_when_none_is_running(host, make_agent, socket):
    host.responses = {LIST: [NOT_RUNNING, NO_KEYS], start(socket): 0}

    make_agent().ensure_running()

    assert host.commands == [LIST, start(socket), LIST]


def test_reuses_a_running_agent(host, make_agent):
    host.responses = {LIST: NO_KEYS}

    make_agent().ensure_running()

    assert host.commands == [LIST]


def test_removes_a_stale_socket_before_starting(host, make_agent, socket):
    host.responses = {LIST: [NOT_RUNNING, NO_KEYS], start(socket): 0}
    socket.parent.mkdir(mode=0o700)
    socket.write_text("stale")  # left behind by a dead agent

    make_agent().ensure_running()

    assert socket.read_text() != "stale"


def test_a_reused_agent_is_touched(host, make_agent, socket):
    host.responses = {LIST: NO_KEYS}
    socket.parent.mkdir(mode=0o700)
    socket.touch()
    an_hour_ago = time.time() - 3600
    os.utime(socket, (an_hour_ago, an_hour_ago))

    make_agent().ensure_running()

    assert time.time() - socket.stat().st_mtime < 60


# --- the socket's private directory, made so on every ensure_running ----------


def test_the_sockets_directory_is_created_for_the_owner_only(host, make_agent, socket):
    host.responses = {LIST: NO_KEYS}

    make_agent().ensure_running()

    assert socket.parent.stat().st_mode & 0o777 == 0o700


def test_the_sockets_directory_has_existing_permissions_tightened(host, make_agent, socket):
    host.responses = {LIST: NO_KEYS}
    socket.parent.mkdir(mode=0o755)

    make_agent().ensure_running()

    assert socket.parent.stat().st_mode & 0o777 == 0o700


def test_a_sockets_directory_owned_by_someone_else_is_refused(host, make_agent):
    with pytest.raises(SandboxError, match="not a directory owned by you"):
        make_agent(uid=os.getuid() + 1).ensure_running()
    assert host.calls == []  # refused before asking any agent


def test_a_sockets_directory_that_is_a_symlink_is_refused_and_its_target_untouched(make_agent, socket, tmp_path):
    target = tmp_path / "elsewhere"
    target.mkdir(mode=0o755)
    socket.parent.symlink_to(target)

    with pytest.raises(SandboxError, match="not a directory owned by you"):
        make_agent().ensure_running()
    assert target.stat().st_mode & 0o777 == 0o755


@pytest.mark.parametrize("make_path", [Path.touch, lambda path: path.symlink_to(path.with_name("missing"))])
def test_a_sockets_directory_that_is_a_file_or_a_dangling_symlink_is_refused(make_agent, socket, make_path):
    make_path(socket.parent)

    with pytest.raises(SandboxError, match="not a directory owned by you"):
        make_agent().ensure_running()


@pytest.mark.parametrize("start_exit, list_after", [(0, NOT_RUNNING), (1, NO_KEYS)])
def test_reports_an_agent_that_fails_to_start(host, make_agent, socket, start_exit, list_after):
    host.responses = {LIST: [NOT_RUNNING, list_after], start(socket): start_exit}

    with pytest.raises(SandboxError, match="ssh-agent failed to start"):
        make_agent().ensure_running()


# --- keys -------------------------------------------------------------------


def test_replace_keys_empties_the_agent_then_adds_each_key(host, make_agent, socket, tmp_path):
    keys = [tmp_path / "id_ed25519", tmp_path / "deploy"]
    host.responses = {DELETE_ALL: 0, **{("ssh-add", "-q", str(key)): 0 for key in keys}}

    make_agent().replace_keys(keys)

    assert host.commands == [DELETE_ALL, *(("ssh-add", "-q", str(key)) for key in keys)]
    assert all(env is not None and env["SSH_AUTH_SOCK"] == str(socket) for _, env in host.calls)


def test_replace_keys_with_no_keys_leaves_the_agent_empty(host, make_agent):
    host.responses = {DELETE_ALL: 0}

    make_agent().replace_keys([])

    assert host.commands == [DELETE_ALL]


def test_reports_an_agent_that_cannot_be_emptied(host, make_agent, tmp_path):
    host.responses = {DELETE_ALL: 1}

    with pytest.raises(SandboxError, match="could not empty the agent"):
        make_agent().replace_keys([tmp_path / "key"])
    assert host.commands == [DELETE_ALL]


def test_reports_a_key_that_cannot_be_added(host, make_agent, tmp_path):
    host.responses = {DELETE_ALL: 0, ("ssh-add", "-q", str(tmp_path / "bad")): 1}

    with pytest.raises(SandboxError, match="ssh-add failed"):
        make_agent().replace_keys([tmp_path / "bad"])


def test_lists_key_fingerprints(host, make_agent):
    host.responses = {LIST: "256 SHA256:a key1 (ED25519)\n256 SHA256:b key2 (ED25519)\n"}

    assert make_agent().list_key_fingerprints() == {"SHA256:a", "SHA256:b"}


def test_lists_no_fingerprints_for_an_empty_agent(host, make_agent):
    host.responses = {LIST: NO_KEYS}

    assert make_agent().list_key_fingerprints() == set()


def test_lists_no_fingerprints_when_the_exit_code_says_so_even_with_stdout(host, make_agent):
    # A real ssh-add never does this; the point is to pin the check on the exit
    # code itself, not on stdout happening to be empty for NO_KEYS in other tests.
    host.responses = {LIST: (NO_KEYS, "256 SHA256:a key1 (ED25519)\n")}

    assert make_agent().list_key_fingerprints() == set()


def test_each_sandbox_gets_an_ssh_agent_on_its_own_socket(host):
    registry = SshAgentRegistry(host, uid=OWN_UID)
    assert registry.ssh_agent("myproj-dev").socket_path == SSH_AGENT_SOCKETS_DIR / "myproj-dev.sock"
    assert registry.ssh_agent("myproj-qa").socket_path == SSH_AGENT_SOCKETS_DIR / "myproj-qa.sock"


def test_list_key_fingerprints_ignores_blank_lines(host, make_agent):
    host.responses = {LIST: "256 SHA256:a key1 (ED25519)\n3072 SHA256:b key2 (RSA)\n"}

    assert make_agent().list_key_fingerprints() == {"SHA256:a", "SHA256:b"}


# --- SshAgentRegistry.prune ---------------------------------------------------

LONG_AGO = 24 * 60 * 60  # older than any recency rule


def make_registry(host, sockets_dir):
    return SshAgentRegistry(host, uid=OWN_UID, sockets_dir=sockets_dir)


def socket_path(sockets_dir, sandbox_name):
    """Where the registry puts a sandbox's socket (test_each_sandbox_gets_an_ssh_agent_on_its_own_socket)."""
    return sockets_dir / f"{sandbox_name}.sock"


def ssh_agent_process(pid, sockets_dir, sandbox_name):
    """How a running agent appears in the process list: the command line it was started with."""
    return (pid, " ".join(start(socket_path(sockets_dir, sandbox_name))))


def socket_touched(sockets_dir, sandbox_name, seconds_ago):
    socket = socket_path(sockets_dir, sandbox_name)
    socket.touch()
    os.utime(socket, (time.time() - seconds_ago,) * 2)


def test_an_ssh_agent_the_registry_started_is_one_it_later_prunes(host, tmp_path):
    sockets_dir = tmp_path / "sockets"
    registry = make_registry(host, sockets_dir)
    ssh_agent = registry.ssh_agent("dev-p-t1")
    host.responses = {LIST: [NOT_RUNNING, NO_KEYS], start(ssh_agent.socket_path): 0}
    ssh_agent.ensure_running()
    started = next(command for command in host.commands if command[0] == "ssh-agent")
    host.processes = [(101, " ".join(started))]
    os.utime(ssh_agent.socket_path, (time.time() - LONG_AGO,) * 2)

    assert registry.prune(live_sandboxes=set()) == ["dev-p-t1"]
    assert host.killed == [101]


def test_ssh_agents_of_sandboxes_not_live_are_pruned(host, tmp_path):
    host.processes = [ssh_agent_process(101, tmp_path, "dev-p-live"), ssh_agent_process(102, tmp_path, "dev-p-old")]
    for name in ("dev-p-live", "dev-p-old"):
        socket_touched(tmp_path, name, LONG_AGO)

    assert make_registry(host, tmp_path).prune(live_sandboxes={"dev-p-live"}) == ["dev-p-old"]
    assert host.killed == [102]


def test_pruning_ignores_every_process_that_is_not_one_of_its_ssh_agents(host, tmp_path):
    host.processes = [
        ssh_agent_process(101, tmp_path, "dev-p-t1"),
        ssh_agent_process(102, tmp_path / "elsewhere", "qa-p-t1"),  # another sockets directory
        (103, "ssh-agent -s"),  # the user's own agent
        (104, "vim notes.md"),
        ssh_agent_process(105, tmp_path, "qa-p-t2"),
    ]
    for name in ("dev-p-t1", "qa-p-t2"):
        socket_touched(tmp_path, name, LONG_AGO)
    (tmp_path / "elsewhere").mkdir()
    socket_touched(tmp_path / "elsewhere", "qa-p-t1", LONG_AGO)

    assert make_registry(host, tmp_path).prune(live_sandboxes=set()) == ["dev-p-t1", "qa-p-t2"]
    assert sorted(host.killed) == [101, 105]


def test_a_recently_launched_ssh_agent_is_spared(host, tmp_path):
    host.processes = [ssh_agent_process(101, tmp_path, "dev-p-new")]
    socket_touched(tmp_path, "dev-p-new", 5)

    assert make_registry(host, tmp_path).prune(live_sandboxes=set()) == []
    assert host.killed == []


def test_an_ssh_agent_that_stopped_meanwhile_is_skipped(host, tmp_path):
    host.processes = [ssh_agent_process(102, tmp_path, "dev-p-gone"), ssh_agent_process(103, tmp_path, "dev-p-old")]
    socket_touched(tmp_path, "dev-p-gone", LONG_AGO)
    socket_touched(tmp_path, "dev-p-old", LONG_AGO)
    host.gone = {102}

    assert make_registry(host, tmp_path).prune(live_sandboxes=set()) == ["dev-p-old"]
    assert host.killed == [103]


def test_an_ssh_agent_whose_socket_is_gone_is_pruned(host, tmp_path):
    host.processes = [ssh_agent_process(101, tmp_path, "dev-p-no-socket")]

    assert make_registry(host, tmp_path).prune(live_sandboxes=set()) == ["dev-p-no-socket"]
    assert host.killed == [101]


def test_a_live_sandboxs_ssh_agent_is_kept_even_without_its_socket(host, tmp_path):
    host.processes = [ssh_agent_process(101, tmp_path, "dev-p-live")]

    assert make_registry(host, tmp_path).prune(live_sandboxes={"dev-p-live"}) == []
    assert host.killed == []


def test_an_orphan_and_its_replacement_on_one_socket_are_both_pruned(host, tmp_path):
    host.processes = [ssh_agent_process(101, tmp_path, "dev-p-t1"), ssh_agent_process(102, tmp_path, "dev-p-t1")]
    socket_touched(tmp_path, "dev-p-t1", LONG_AGO)

    assert make_registry(host, tmp_path).prune(live_sandboxes=set()) == ["dev-p-t1"]
    assert sorted(host.killed) == [101, 102]
