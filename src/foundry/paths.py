"""Where things are in a foundry instance. The only module that builds these paths.

Every function takes the foundry root and returns a path; none of them
checks that the path exists. ``find_foundry_root`` locates the root by
walking up from a starting directory to the one holding config/foundry.yaml,
the way git finds .git.
"""

from pathlib import Path

from foundry.errors import FoundryError

CONFIG_RELATIVE_PATH = Path("config") / "foundry.yaml"


def find_foundry_root(start_dir: Path | None = None) -> Path:
    here = (start_dir or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / CONFIG_RELATIVE_PATH).is_file():
            return candidate
    raise FoundryError(f"not inside a foundry instance: no {CONFIG_RELATIVE_PATH} found from {here} upwards")


def config_path(foundry_root: Path) -> Path:
    return foundry_root / CONFIG_RELATIVE_PATH


def agent_kit_dir(foundry_root: Path) -> Path:
    return foundry_root / "agent-kit"


def ssh_key_path(foundry_root: Path, role_name: str) -> Path:
    return foundry_root / "secrets" / "ssh" / role_name


def github_token_path(foundry_root: Path, role_name: str) -> Path:
    """Optional: a role gets a GitHub token only if this file exists."""
    return foundry_root / "secrets" / "github" / f"{role_name}.token"


def session_dir(foundry_root: Path, sandbox_name: str) -> Path:
    return foundry_root / "sessions" / sandbox_name


def repo_policy_dir(foundry_root: Path) -> Path:
    """The directory holding what every project's repository must match."""
    return foundry_root / "config" / "repo-policy"
