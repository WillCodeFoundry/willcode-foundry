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


def build_runtime(kit_dir: Path) -> Path:
    """Build agent_runtime into ``kit_dir``'s .build/ and return the zipapp's path.

    Atomic: the archive is written beside its final name and renamed over it, so a sandbox running
    while it is built sees the old file or the new one, never part of one. Raises FoundryError if the kit
    is missing or can't be written.
    """
    target = AgentKit(kit_dir).runtime
    if not kit_dir.is_dir():
        raise FoundryError(f"can't build the agent runtime: the agent kit {kit_dir} is missing")
    try:
        target.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="agent-runtime-") as staging_dir:
            staging = Path(staging_dir)
            shutil.copytree(_SOURCE_DIR, staging / "agent_runtime", ignore=_not_python_source)
            descriptor, partial_name = tempfile.mkstemp(dir=target.parent, prefix=f"{target.name}.", suffix=".tmp")
            os.close(descriptor)
            partial = Path(partial_name)
            try:
                zipapp.create_archive(staging, partial, interpreter=None, main="agent_runtime.__main__:main")
                partial.chmod(0o644)  # mkstemp's 0600 would keep the sandbox's user out
                os.replace(partial, target)
            finally:
                partial.unlink(missing_ok=True)
    except OSError as error:
        raise FoundryError(f"can't build the agent runtime into {target}: {error}") from None
    return target


def _not_python_source(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if not name.endswith(".py") or name == "__pycache__"}
