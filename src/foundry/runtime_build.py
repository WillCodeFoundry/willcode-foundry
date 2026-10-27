"""Building agent_runtime into an agent kit, as the zipapp its sandboxes run.

The runtime is run from the kit's read-only mount, never copied into the sandbox, so building it into
the kit at every launch is how a sandbox gets the runtime of the foundry that launches it.
"""

import os
import shutil
import tempfile
import zipapp
from pathlib import Path

import agent_runtime
from agent_runtime.agent_kit import AgentKit
from foundry.errors import FoundryError

_SOURCE_DIR = Path(agent_runtime.__file__).parent


def build_runtime(kit_dir: Path, *, source: Path = _SOURCE_DIR) -> Path:
    """Build the agent_runtime package at ``source`` into ``kit_dir``'s .build/ and return the zipapp's path.

    Every .py file of the package goes in, in its folders. The archive is written beside its final name and
    renamed over it, so a sandbox that already has the old file open keeps reading all of it. When the source
    hasn't changed, the archive comes out the same and the old file is left in place. A process starting just
    as a changed runtime lands can still fail to import, since zipimport reopens the archive by path; a launch
    after a change to the runtime is when that can happen. Raises FoundryError if the kit is missing or can't
    be written.
    """
    target = AgentKit(kit_dir).runtime
    if not kit_dir.is_dir():
        raise FoundryError(f"can't build the agent runtime: the agent kit {kit_dir} is missing")
    try:
        target.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="agent-runtime-") as staging_dir:
            staging = Path(staging_dir)
            shutil.copytree(source, staging / "agent_runtime", ignore=_not_python_source)
            descriptor, partial_name = tempfile.mkstemp(dir=target.parent, prefix=f"{target.name}.", suffix=".tmp")
            os.close(descriptor)
            partial = Path(partial_name)
            try:
                zipapp.create_archive(staging, partial, interpreter=None, main="agent_runtime.__main__:main")
                if not (target.is_file() and target.read_bytes() == partial.read_bytes()):
                    partial.chmod(0o644)  # mkstemp's 0600 would keep the sandbox's user out
                    os.replace(partial, target)
            finally:
                partial.unlink(missing_ok=True)
    except OSError as error:
        raise FoundryError(f"can't build the agent runtime into {target}: {error}") from None
    return target


def _not_python_source(directory: str, names: list[str]) -> set[str]:
    """What copytree leaves out: caches, and files that aren't Python. Folders go in, for their .py files."""
    return {
        name
        for name in names
        if name == "__pycache__" or (not name.endswith(".py") and not (Path(directory) / name).is_dir())
    }
