"""Where things are in a foundry instance. The only module that builds these paths.

Every function takes the instance root and returns a path; none of them
checks that the path exists. ``find_root`` locates the root by walking up
from a starting directory to the one holding config/foundry.yaml, the way
git finds .git.
"""

from pathlib import Path

from foundry.errors import FoundryError

CONFIG_FILE = Path("config") / "foundry.yaml"


def find_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / CONFIG_FILE).is_file():
            return candidate
    raise FoundryError(f"not inside a foundry instance: no {CONFIG_FILE} found from {here} upwards")


def config_file(root: Path) -> Path:
    return root / CONFIG_FILE


def kit(root: Path) -> Path:
    return root / "agent-kit"


def ssh_key(root: Path, role: str) -> Path:
    return root / "secrets" / "ssh" / role


def github_token(root: Path, role: str) -> Path:
    """Optional: a role gets a GitHub token only if this file exists."""
    return root / "secrets" / "github" / f"{role}.token"


def sessions(root: Path) -> Path:
    return root / "sessions"


def session_dir(root: Path, name: str) -> Path:
    return sessions(root) / name
