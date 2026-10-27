"""session-setup as delivered: the built pyz, with a sandbox's variables, against a local origin.

What only this shows: the command runs from the built kit and sets the checkouts up there. Its rules are
tested in-process, in tests/agent_runtime/test_session_setup.py.
"""

import os
import subprocess
from pathlib import Path

from foundry.task import NOTES_BRANCH
from tests.support import TASK, git
from tests.support.kit import runtime_command


def session_setup(kit_env: dict[str, str], origin: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **kit_env, "AGENT_REPO_URL": f"file://{origin}"}
    return subprocess.run(
        runtime_command(Path(env["AGENT_KIT_DIR"]), "session-setup"),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_created_task_gets_both_checkouts_with_the_kits_hooks(built_kit, kit_env, created_task) -> None:
    env = kit_env(TASK)

    result = session_setup(env, created_task)

    assert result.returncode == 0, result.stderr
    code, notes = Path(env["AGENT_PROJECT_DIR"]), Path(env["AGENT_NOTES_DIR"])
    assert git(code, "branch", "--show-current").stdout.strip() == TASK.branch
    assert git(notes, "branch", "--show-current").stdout.strip() == NOTES_BRANCH
    assert (notes / TASK.task_file).read_text() == "# Task\n"
    assert git(code, "config", "core.hooksPath").stdout.strip() == str(built_kit / "hooks")
