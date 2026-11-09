"""A foundry of a test's own: its config, and its roles in its agent-kit."""

from collections.abc import Iterable, Mapping
from pathlib import Path


def write_foundry(root: Path, projects: Mapping[str, str | Path], roles: Iterable[str] = ()) -> Path:
    """A foundry at ``root``: config/foundry.yaml with ``projects`` by URL and ``roles`` with no settings, and each
    role's ROLE.md and gitconfig. Returns ``root``."""
    project_lines = "".join(f"  {name}: {{url: '{url}'}}\n" for name, url in projects.items())
    role_lines = "".join(f"\n  {name}: {{}}" for name in roles) or " {}"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "foundry.yaml").write_text(f"name: f\nprojects:\n{project_lines}roles:{role_lines}\n")
    for name in roles:
        role_dir = root / "agent-kit" / "roles" / name
        role_dir.mkdir(parents=True)
        (role_dir / "ROLE.md").write_text(f"{name}\n")
        (role_dir / "gitconfig").write_text("")
    return root
