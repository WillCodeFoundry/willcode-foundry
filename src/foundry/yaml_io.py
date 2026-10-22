"""Reading the foundry's YAML files, with errors a user can act on."""

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
