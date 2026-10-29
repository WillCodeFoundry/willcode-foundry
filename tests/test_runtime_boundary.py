"""foundry imports six runtime modules and no others: the sandbox's code stays the sandbox's, and ARCHITECTURE.md's
rule is checked rather than only stated."""

import ast
from pathlib import Path

FOUNDRY_DIR = Path(__file__).parents[1] / "src" / "foundry"
SHARED = {
    "agent_runtime.contract",
    "agent_runtime.agent_kit",
    "agent_runtime.atomic_files",
    "agent_runtime.git",
    "agent_runtime.task.lifecycles",
    "agent_runtime.task.state",
}
"""What both packages use: the session variables, the kit's layout, replacing files, running git, and the
lifecycles and task states. Never agent_runtime.task.command, which runs only in the sandbox."""


def runtime_imports(module_path: Path) -> set[str]:
    """The agent_runtime modules a foundry module imports, each by its full name."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(module_path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names if alias.name.split(".")[0] == "agent_runtime")
        elif isinstance(node, ast.ImportFrom) and node.module == "agent_runtime":
            names.update(f"agent_runtime.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("agent_runtime."):
            names.add(node.module)
    return names


def test_foundry_imports_only_the_shared_runtime_modules() -> None:
    imported = {
        f"{path.relative_to(FOUNDRY_DIR)}: {name}"
        for path in FOUNDRY_DIR.rglob("*.py")
        for name in runtime_imports(path)
    }
    # runtime_build imports the package itself, to find the source it builds.
    outside = {
        line for line in imported if line.split(": ")[1] not in SHARED and line != "runtime_build.py: agent_runtime"
    }

    assert outside == set()
    assert {line.split(": ")[1] for line in imported} >= SHARED  # each is still used: ARCHITECTURE.md's list is current
