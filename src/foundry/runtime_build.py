"""Building agent_runtime into an agent kit, as the zipapp its sandboxes run.

The runtime is run from the kit's read-only mount, never copied into the sandbox, so building it into
the kit at every launch is how a sandbox gets the runtime of the foundry that launches it.
"""

import io
import zipfile
from pathlib import Path, PurePosixPath
from typing import Final

import agent_runtime
from agent_runtime.agent_kit import AgentKit
from agent_runtime.atomic_files import atomic_write
from foundry.errors import FoundryError

_SOURCE_DIR = Path(agent_runtime.__file__).parent

_MAIN_PY: Final = "# -*- coding: utf-8 -*-\nimport agent_runtime.__main__\nagent_runtime.__main__.main()\n"
"""The archive's entry point, as zipapp writes it for ``agent_runtime.__main__:main``."""

_ENTRY_TIME: Final = (1980, 1, 1, 0, 0, 0)
"""Every entry's timestamp: the earliest a zip can hold, so no file's modification time reaches the bytes."""


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
    """The zipapp of the package at ``source``: the same bytes for the same files, whatever order or time they
    were written in.

    Written here rather than by zipapp: Python 3.11's zipapp adds files in the order the file system lists them,
    and stamps each with its modification time, so two builds of unchanged source could differ.
    """
    files = sorted(
        PurePosixPath("agent_runtime", path.relative_to(source).as_posix())
        for path in source.rglob("*.py")
        if "__pycache__" not in path.relative_to(source).parts
    )
    folders = sorted({folder for file in files for folder in file.parents if folder != PurePosixPath(".")})
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        for folder in folders:
            zip_file.writestr(_entry(f"{folder}/", mode=0o40755), b"")
        for file in files:
            zip_file.writestr(
                _entry(str(file), mode=0o100644), (source / file.relative_to("agent_runtime")).read_bytes()
            )
        zip_file.writestr(_entry("__main__.py", mode=0o100644), _MAIN_PY)
    return archive.getvalue()


def _entry(name: str, *, mode: int) -> zipfile.ZipInfo:
    """A zip entry named ``name``, with ``mode``, stamped _ENTRY_TIME."""
    entry = zipfile.ZipInfo(name, date_time=_ENTRY_TIME)
    entry.external_attr = mode << 16
    return entry
