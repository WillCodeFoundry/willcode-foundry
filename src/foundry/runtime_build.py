"""Building agent_runtime into an agent kit, as the zipapp its sandboxes run.

The runtime is run from the kit's read-only mount, never copied into the sandbox, so building it into
the kit at every launch is how a sandbox gets the runtime of the foundry that launches it.
"""

import io
import shutil
import tempfile
import zipapp
from pathlib import Path

import agent_runtime
from agent_runtime.agent_kit import AgentKit
from agent_runtime.files import atomic_write
from foundry.errors import FoundryError

_SOURCE_DIR = Path(agent_runtime.__file__).parent


def build_runtime(agent_kit_dir: Path, *, source: Path = _SOURCE_DIR) -> Path:
    """Build the agent_runtime package at ``source`` into the kit's .build/ and return the zipapp's path.

    Every .py file of the package goes in, in its folders. An unchanged archive leaves the old file in place;
    a changed one replaces it whole. Raises FoundryError if the kit is missing or can't be written.
    """
    target = AgentKit(agent_kit_dir).runtime
    if not agent_kit_dir.is_dir():
        raise FoundryError(f"can't build the agent runtime: the agent kit {agent_kit_dir} is missing")
    try:
        archive = _archive(source)
        target.parent.mkdir(exist_ok=True)
        # zipimport reopens the archive by path: a process starting as a changed one lands may fail to import.
        if not (target.is_file() and target.read_bytes() == archive):
            atomic_write(target, archive)
    except OSError as error:
        raise FoundryError(f"can't build the agent runtime into {target}: {error}") from None
    return target


def _archive(source: Path) -> bytes:
    """The zipapp of the package at ``source``: the same bytes for the same files."""
    with tempfile.TemporaryDirectory(prefix="agent-runtime-") as staging_dir:
        staging = Path(staging_dir)
        shutil.copytree(source, staging / "agent_runtime", ignore=_not_python_source)
        archive = io.BytesIO()
        zipapp.create_archive(staging, archive, interpreter=None, main="agent_runtime.__main__:main")
        return archive.getvalue()


def _not_python_source(directory: str, names: list[str]) -> set[str]:
    """What copytree leaves out: caches, and files that aren't Python. Folders go in, for their .py files."""
    return {
        name
        for name in names
        if name == "__pycache__" or (not name.endswith(".py") and not (Path(directory) / name).is_dir())
    }
