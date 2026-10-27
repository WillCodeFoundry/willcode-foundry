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

from tests.agent_kit.conftest import runtime_command
from tests.conftest import TASK


def launch(
    tmp_path: Path, kit_env, created_task: Path, *, sudo_script: str, sudo_mode: int
) -> subprocess.CompletedProcess[str]:
    """session-init, as the launcher runs it, through the built pyz, with a stand-in sudo of ``sudo_script`` at
    ``sudo_mode`` and git alone on PATH, so no other sudo can run."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sudo = bin_dir / "sudo"
    sudo.write_text(sudo_script)
    sudo.chmod(sudo_mode)
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    path = str(bin_dir)
    # The stand-in, if it can run, is the only sudo this run can reach: the real one is out of reach.
    assert shutil.which("sudo", path=path) in (None, str(sudo))
    env = {**os.environ, **kit_env(TASK), "AGENT_REPO_URL": f"file://{created_task}", "PATH": path}
    return subprocess.run(
        runtime_command(Path(env["AGENT_KIT_DIR"]), "session-init"),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_relaunch_after_hardening_goes_on_to_verify(tmp_path: Path, kit_env, created_task: Path) -> None:
    """Every launch after the first: the bare `sudo` looked up on PATH can't execute, since root mode left it
    mode 0. It must count as no sudo, so session-init skips root mode and verifies, rather than stopping with
    a traceback."""
    result = launch(tmp_path, kit_env, created_task, sudo_script="#!/bin/sh\nexit 0\n", sudo_mode=0)

    assert "Traceback" not in result.stderr
    assert "session-setup: checkouts ready" in result.stdout
    # This machine isn't a hardened sandbox, so verify refuses.
    assert result.returncode == 1
    assert "harden --verify: " in result.stderr
    assert "harden: " not in result.stderr  # root mode never ran


def first_launch(
    tmp_path: Path, kit_env, created_task: Path, root_exit_code: int
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """session-init on a sandbox whose sudo still works: a stand-in that exits 0 for `sudo -n true`, and for any
    other call records its arguments, one line per call, and exits with ``root_exit_code``. It never runs what
    it is given. Returns the run and the stand-in's record."""
    record = tmp_path / "sudo.calls"
    script = (
        f'#!/bin/sh\n[ "$*" = "-n true" ] && exit 0\nprintf \'%s\\n\' "$*" >> \'{record}\'\nexit {root_exit_code}\n'
    )
    return launch(tmp_path, kit_env, created_task, sudo_script=script, sudo_mode=0o755), record


def test_a_first_launch_sets_up_runs_root_mode_through_sudo_then_verifies(
    tmp_path: Path, kit_env, created_task: Path
) -> None:
    """sudo still works on the first launch: root mode runs through it, given AGENT_KIT_DIR alone, then verify."""
    kit_dir = Path(kit_env(TASK)["AGENT_KIT_DIR"])

    result, record = first_launch(tmp_path, kit_env, created_task, root_exit_code=0)

    assert "Traceback" not in result.stderr
    assert "session-setup: checkouts ready" in result.stdout
    assert record.read_text().splitlines() == [
        f"--preserve-env=AGENT_KIT_DIR /usr/bin/python3 -IS {kit_dir / '.build' / 'agent_runtime.pyz'} harden"
    ]
    # This machine isn't a hardened sandbox, so verify refuses.
    assert "harden --verify: " in result.stderr
    assert result.returncode == 1


def test_a_failing_root_mode_stops_the_launch_before_verify(tmp_path: Path, kit_env, created_task: Path) -> None:
    result, record = first_launch(tmp_path, kit_env, created_task, root_exit_code=3)

    assert len(record.read_text().splitlines()) == 1
    assert result.returncode == 3
    assert "harden --verify: " not in result.stderr
