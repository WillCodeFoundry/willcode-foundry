"""Reading and writing the foundry's YAML files, with errors a user can act on."""

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
    """Write atomically: a crash mid-write leaves the old file, never a partial one."""
    temporary_path = file_path.with_name(f".{file_path.name}.tmp")
    temporary_path.write_text(yaml.safe_dump(data, sort_keys=False))
    temporary_path.replace(file_path)
