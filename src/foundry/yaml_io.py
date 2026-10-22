"""Reading and writing the foundry's YAML files, with errors a user can act on."""

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from foundry.errors import FoundryError


def load(file_path: Path) -> Any:
    try:
        return yaml.safe_load(file_path.read_text())
    except FileNotFoundError:
        raise FoundryError(f"{file_path} is missing") from None
    except yaml.YAMLError as error:
        raise FoundryError(f"{file_path} is not valid YAML: {error}") from None


def dump(file_path: Path, data: Any) -> None:
    """Write atomically: a crash mid-write leaves the old file, never a partial one.

    The temporary file is unique to this write, so two writers can't share it;
    the last to finish wins, whole.
    """
    descriptor, temporary_name = tempfile.mkstemp(dir=file_path.parent, prefix=f".{file_path.name}.", suffix=".tmp")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as temporary_file:
            temporary_file.write(yaml.safe_dump(data, sort_keys=False))
        temporary_path.replace(file_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
