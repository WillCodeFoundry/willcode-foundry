"""The runtime's session-init, as the launcher runs it, from the built kit against a local origin: on a first
launch, while sudo still works, and on a relaunch, after hardening has left it unable to run.

Everything runs for real except sudo, the system boundary: git against a temporary origin, files under a
throwaway HOME, and verify's read-only checks. sudo is a stand-in. On a first launch it answers the probe,
and records any other call without running it; on a relaunch it is mode 0, as the first launch's hardening
leaves the real one. PATH holds only it and git: the exec search skips an entry it can't execute and tries
the next, so with the machine's own PATH after it, the real sudo would run.
"""

import os
import shutil
import subprocess
from pathlib import Path

from tests.agent_kit.conftest import TASK, runtime_command


def test_a_relaunch_after_hardening_goes_on_to_verify(tmp_path: Path, kit_env, created_task: Path) -> None:
    """The path review finding R12 broke: the bare `sudo` looked up on PATH can't execute. It must count as
    no sudo, so session-init skips root mode and verifies, rather than stopping with a traceback."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sudo = bin_dir / "sudo"
    sudo.write_text("#!/bin/sh\nexit 0\n")
    sudo.chmod(0)
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    path = str(bin_dir)
    assert shutil.which("sudo", path=path) is None  # no sudo this run can execute: the real one is out of reach
    env = {**os.environ, **kit_env(TASK), "AGENT_REPO_URL": f"file://{created_task}", "PATH": path}

    result = subprocess.run(
        runtime_command(Path(env["AGENT_KIT_DIR"]), "session-init"),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert "Traceback" not in result.stderr
    assert "session-setup: checkouts ready" in result.stdout
    # This machine isn't a hardened sandbox, so verify refuses: as root before its checks, otherwise after them.
    assert result.returncode == 1
    assert "harden --verify: " in result.stderr
    assert "harden: " not in result.stderr  # root mode never ran


def first_launch(
    tmp_path: Path, kit_env, created_task: Path, root_exit_code: int
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """session-init on a sandbox whose sudo still works: a stand-in that exits 0 for `sudo -n true`, and for any
    other call records its arguments, one line per call, and exits with ``root_exit_code``. It never runs what
    it is given. Returns the run and the stand-in's record."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    record = tmp_path / "sudo.calls"
    sudo = bin_dir / "sudo"
    sudo.write_text(
        f'#!/bin/sh\n[ "$*" = "-n true" ] && exit 0\nprintf \'%s\\n\' "$*" >> \'{record}\'\nexit {root_exit_code}\n'
    )
    sudo.chmod(0o755)
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    path = str(bin_dir)
    assert shutil.which("sudo", path=path) == str(sudo)  # the stand-in is the only sudo this run can reach
    env = {**os.environ, **kit_env(TASK), "AGENT_REPO_URL": f"file://{created_task}", "PATH": path}

    result = subprocess.run(
        runtime_command(Path(env["AGENT_KIT_DIR"]), "session-init"),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, record


def test_a_first_launch_sets_up_runs_root_mode_through_sudo_then_verifies(
    tmp_path: Path, kit_env, created_task: Path
) -> None:
    """sudo still works on the first launch: root mode runs through it, given AGENT_KIT_DIR alone, then verify."""
    kit_dir = Path(kit_env(TASK)["AGENT_KIT_DIR"])

    result, record = first_launch(tmp_path, kit_env, created_task, root_exit_code=0)

    assert "Traceback" not in result.stderr
    assert "session-setup: checkouts ready" in result.stdout
    assert record.read_text().splitlines() == [
        f"--preserve-env=AGENT_KIT_DIR /usr/bin/python3 -I {kit_dir / '.build' / 'agent_runtime.pyz'} harden"
    ]
    # This machine isn't a hardened sandbox, so verify refuses: as root before its checks, otherwise after them.
    assert "harden --verify: " in result.stderr
    assert result.returncode == 1


def test_a_failing_root_mode_stops_the_launch_before_verify(tmp_path: Path, kit_env, created_task: Path) -> None:
    result, record = first_launch(tmp_path, kit_env, created_task, root_exit_code=3)

    assert len(record.read_text().splitlines()) == 1
    assert result.returncode == 3
    assert "harden --verify: " not in result.stderr
