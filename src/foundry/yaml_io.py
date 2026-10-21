"""Reading and writing the foundry's YAML files, with errors a user can act on."""

from pathlib import Path
from typing import Any

import yaml

from foundry.errors import FoundryError


def load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise FoundryError(f"{path} is missing") from None
    except yaml.YAMLError as error:
        raise FoundryError(f"{path} is not valid YAML: {error}") from None


def dump(path: Path, data: Any) -> None:
    """Write atomically: a crash mid-write leaves the old file, never a partial one."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=False))
    tmp.replace(path)
