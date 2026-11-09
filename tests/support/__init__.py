"""Helpers the tests share: plain functions and constants. Fixtures and pytest hooks stay in the conftests."""

import os
import subprocess
import sys
from collections.abc import Callable, Mapping, MutableMapping
from pathlib import Path

import pytest

from agent_runtime import contract
from foundry.task import Task

REPOSITORY = Path(__file__).parents[2]
AGENT_KIT_SOURCE = REPOSITORY / "agent-kit"


SANDBOX_IMAGE = pytest.StashKey[str]()
"""The template image a -m docker run tested, digest included: recorded by tests/sandbox_image's image fixture,
printed below. pytest honours summary hooks only in this, the root conftest."""


TASK = Task.as_open("tst-0001")


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


VariablesFor = Callable[[Path, Path], contract.SessionVariables]
"""Makes the session variables a sandbox for TASK gets, given the kit's dir and a local origin's."""

UNSIGNED = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "commit.gpgsign", "GIT_CONFIG_VALUE_0": "false"}
"""git's environment override turning commit signing off, which beats any config file: the roles sign with keys
whose private halves the tests don't have."""


UNREACHABLE_PROXY = "http://127.0.0.1:9"
"""A proxy nothing listens on: a request that reaches for the network fails at once rather than going out."""

PROXY_VARIABLES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def isolate_from_the_developer(environ: MutableMapping[str, str], home: Path) -> None:
    """Make ``environ`` a fresh machine's, so a test that passes in it passes on any machine.

    | Left out | How |
    |---|---|
    | The developer's home and git configuration | ``home`` as HOME, holding XDG_CONFIG_HOME and GIT_CONFIG_GLOBAL |
    | The system's git configuration | GIT_CONFIG_NOSYSTEM |
    | SSH and GPG agents, which sign commits | their variables unset, and GNUPGHOME in ``home`` |
    | The network | git allowed only local repositories, and every proxy variable pointed at a closed port |"""
    (home / ".gitconfig").touch()
    environ.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GNUPGHOME": str(home / ".gnupg"),
            "GIT_ALLOW_PROTOCOL": "file",
            **dict.fromkeys(
                ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"), UNREACHABLE_PROXY
            ),
        }
    )
    for name in ("SSH_AUTH_SOCK", "GPG_AGENT_INFO", "NO_PROXY", "no_proxy"):
        environ.pop(name, None)
