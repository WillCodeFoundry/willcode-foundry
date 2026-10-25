"""agent_sandbox imports nothing from the rest of foundry, so it could be lifted out unchanged."""

import ast
from pathlib import Path

PACKAGE_DIR = Path(__file__).parents[2] / "src" / "foundry" / "agent_sandbox"


def imported_modules(module_path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(module_path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        # Relative imports are banned by ruff (TID252), so checking absolute
        # imports covers every import.
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.add(node.module)
    return names


def test_agent_sandbox_imports_nothing_from_the_rest_of_foundry() -> None:
    outside = {
        f"{path.name}: {name}"
        for path in PACKAGE_DIR.glob("*.py")
        for name in imported_modules(path)
        if (name == "foundry" or name.startswith("foundry.")) and not name.startswith("foundry.agent_sandbox")
    }
    assert outside == set()
