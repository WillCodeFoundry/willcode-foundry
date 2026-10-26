"""The runtime's session-init, as the launcher runs it on a relaunch, from the built kit against a local origin.

Everything runs for real except sudo, the system boundary: git against a temporary origin, files under a
throwaway HOME, and verify's read-only checks. sudo is a stand-in, left mode 0 as the first launch's hardening
leaves the real one. PATH holds only it and git: the exec search skips an entry it can't execute and tries the
next, so with the machine's own PATH after it, the real sudo would run.
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
