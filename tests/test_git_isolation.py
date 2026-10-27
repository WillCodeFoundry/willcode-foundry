"""The suite's git runs against throwaway configuration, whatever the developer's environment points git at.

Each case runs a part of the suite that writes global git config, in a pytest of its own, with a variable
exported as a developer's shell might, and checks the developer's own file is unchanged and the run passed.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).parents[1]
DEVELOPERS_CONFIG = "[user]\n\tname = Real Dev\n\temail = real@example.com\n"


def run_suite_part(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "tests/agent_runtime/test_git.py"],
        cwd=REPOSITORY,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("variable", ["XDG_CONFIG_HOME", "GIT_CONFIG_GLOBAL"])
def test_the_developers_global_config_is_left_alone(tmp_path: Path, variable: str) -> None:
    developer = tmp_path / "developer"
    xdg_config = developer / "git" / "config"
    xdg_config.parent.mkdir(parents=True)
    xdg_config.write_text(DEVELOPERS_CONFIG)
    value = {"XDG_CONFIG_HOME": str(developer), "GIT_CONFIG_GLOBAL": str(xdg_config)}[variable]

    run = run_suite_part({variable: value})

    assert run.returncode == 0, run.stdout + run.stderr
    assert xdg_config.read_text() == DEVELOPERS_CONFIG


def test_a_repository_the_environment_names_is_ignored(tmp_path: Path) -> None:
    """As when the suite runs from a git hook, which exports GIT_DIR and GIT_INDEX_FILE."""
    run = run_suite_part({"GIT_DIR": str(tmp_path / "elsewhere.git"), "GIT_INDEX_FILE": str(tmp_path / "index")})

    assert run.returncode == 0, run.stdout + run.stderr
