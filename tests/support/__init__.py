"""Helpers the tests share: plain functions and constants. Fixtures and pytest hooks stay in the conftests."""

import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from agent_runtime import contract
from foundry.task import Task

REPOSITORY = Path(__file__).parents[2]
AGENT_KIT_SOURCE = REPOSITORY / "agent-kit"


SANDBOX_IMAGE = pytest.StashKey[str]()
"""The template image a -m docker run tested, digest included: recorded by tests/sandbox_image's image fixture,
printed below. pytest honours summary hooks only in this, the root conftest."""


TASK = Task("T1")


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """``git *args`` in ``cwd``, its output captured as text; a failure raises unless ``check`` is False."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def run_pytest(*args: str, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """pytest in a process of its own, in this repository, with this one's environment plus ``env``."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=REPOSITORY,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


SessionFor = Callable[[Path, Path], contract.Environ]
"""Makes the session a sandbox for TASK gets, given the kit's folder and a local origin's."""

UNSIGNED = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "commit.gpgsign", "GIT_CONFIG_VALUE_0": "false"}
"""git's environment override turning commit signing off, which beats any config file: the roles sign with keys
whose private halves the tests don't have."""
