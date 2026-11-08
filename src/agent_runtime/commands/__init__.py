"""The runtime's commands, one module per command that ``__main__`` dispatches to.

Each command is a composition root, as design rule 7 says. It reads what this process was given (the session
variables, stdin, the hook's arguments), calls the library, and prints the result. The modules above this package
return results or raise, and never print; only this package and ``__main__`` may.
"""

import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from agent_runtime import contract

_RUNTIME_LOGGER = logging.getLogger("agent_runtime")


@contextmanager
def progress_on_stdout() -> Iterator[None]:
    """Show the library's progress on stdout while one command runs, where git's own output goes too.

    The handler and level are removed afterwards, so nothing carries over to the next command run in-process.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    previous_level = _RUNTIME_LOGGER.level
    _RUNTIME_LOGGER.addHandler(handler)
    _RUNTIME_LOGGER.setLevel(logging.INFO)
    try:
        yield
    finally:
        _RUNTIME_LOGGER.removeHandler(handler)
        _RUNTIME_LOGGER.setLevel(previous_level)


def read_agent_kit_dir() -> Path:
    """AGENT_KIT_DIR, the one session variable the hardening commands are given."""
    contract.require_set(os.environ, [contract.KIT_DIR])
    return Path(os.environ[contract.KIT_DIR])
