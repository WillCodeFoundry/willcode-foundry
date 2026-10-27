"""session-init as delivered: the built pyz, run as the launcher runs it, handing root mode to sudo.

What only this shows: the exact command session-init hands sudo, the runtime's isolated interpreter and the kit
alone preserved, through the real exec of a sudo found on PATH. The order of the launch, and what root mode and
the check do, are tested in-process, in tests/agent_runtime/test_session_init.py.

sudo is a stand-in that answers the probe, and records any other call without running it. PATH holds only it
and git: the exec search skips an entry it can't execute and tries the next, so with the machine's own PATH
after it, the real sudo would run.
"""

import os
import shutil
import subprocess
from pathlib import Path

from tests.support import TASK
from tests.support.kit import runtime_command


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


def test_a_first_launch_sets_up_runs_root_mode_through_sudo_then_checks(
    tmp_path: Path, kit_env, created_task: Path
) -> None:
    """sudo still works on the first launch: root mode runs through it, given AGENT_KIT_DIR alone, then the check."""
    kit_dir = Path(kit_env(TASK)["AGENT_KIT_DIR"])

    result, record = first_launch(tmp_path, kit_env, created_task, root_exit_code=0)

    assert "Traceback" not in result.stderr
    assert "session-setup: checkouts ready" in result.stdout
    assert record.read_text().splitlines() == [
        f"--preserve-env=AGENT_KIT_DIR /usr/bin/python3 -IS {kit_dir / '.build' / 'agent_runtime.pyz'} harden"
    ]
    # This machine isn't a hardened sandbox, so the check refuses.
    assert "check-hardening: " in result.stderr
    assert result.returncode == 1
