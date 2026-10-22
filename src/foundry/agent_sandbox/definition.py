"""The sandbox definition: sbxenv.yaml, what sbx creates a sandbox from.

The only module that knows sbx's file format. A definition is written once,
when a sandbox is first created, and read back on every launch: sbx fixes a
sandbox's mounts at creation, so the file must not change afterwards.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from foundry.agent_sandbox.errors import SandboxError

DEFINITION_FILE_NAME = "sbxenv.yaml"
"""The file sbx reads from a directory passed to ``sbx env``."""


@dataclass(frozen=True)
class SandboxDefinition:
    name: str
    workspace_dir: Path
    """An empty directory: sbx requires a primary workspace before it accepts others; nothing goes in it."""
    agent_kit_dir: Path
    """Mounted read-only, as the sandbox's one additional workspace."""
    variables: Mapping[str, str]
    """Environment variables set inside the sandbox."""


def write(definition_dir: Path, definition: SandboxDefinition) -> None:
    """Write sbxenv.yaml in sbx's schema.

    Not atomic: it is written once, into a directory just created for it, so
    there's no earlier version to protect.
    """
    document = {
        "schemaVersion": "1",
        "name": definition.name,
        "agent": "claude",
        "workspace": str(definition.workspace_dir),
        "additionalWorkspaces": [{"path": str(definition.agent_kit_dir), "readOnly": True}],
        "env": dict(definition.variables),
    }
    (definition_dir / DEFINITION_FILE_NAME).write_text(yaml.safe_dump(document, sort_keys=False))


def read(definition_dir: Path) -> SandboxDefinition:
    """Read sbxenv.yaml back; anything foundry didn't write fails with one message naming the file."""
    definition_path = definition_dir / DEFINITION_FILE_NAME
    try:
        document = yaml.safe_load(definition_path.read_text())
        (agent_kit,) = document["additionalWorkspaces"]
        return SandboxDefinition(
            name=str(document["name"]),
            workspace_dir=Path(document["workspace"]),
            agent_kit_dir=Path(agent_kit["path"]),
            variables={str(key): str(value) for key, value in document["env"].items()},
        )
    except FileNotFoundError:
        raise SandboxError(f"{definition_path} is missing") from None
    except (yaml.YAMLError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise SandboxError(f"{definition_path}: not a sandbox definition written by foundry ({error!r})") from None
