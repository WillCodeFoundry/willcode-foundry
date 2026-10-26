"""The built agent runtime, run as the kit's hooks and the launcher run it: ``python -I <pyz> ...``."""

import ast
import os
import subprocess
import sys
from pathlib import Path

from agent_runtime import contract
from foundry import paths
from tests.agent_kit.conftest import runtime_command

RUNTIME_SOURCE = Path(__file__).parents[2] / "src" / "agent_runtime"


def run_python(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-I", *args], capture_output=True, text=True, check=False)


def test_the_runtime_imports_only_the_standard_library(built_kit: Path) -> None:
    """Every module of the package, imported from the zipapp, loads nothing outside the standard library: neither
    foundry nor yaml, nor anything else installed, has to be in the sandbox. (What the interpreter's own site
    loads before, a virtualenv's for one, isn't the runtime's.)"""
    pyz = paths.runtime_pyz(built_kit)
    modules = sorted(path.stem for path in RUNTIME_SOURCE.glob("*.py") if path.stem != "__main__")
    code = "\n".join(
        [
            "import sys",
            "before = set(sys.modules)",
            f"sys.path.insert(0, {str(pyz)!r})",
            *(f"import agent_runtime.{module}" for module in modules),
            "import agent_runtime.__main__",
            "top = {name.partition('.')[0] for name in set(sys.modules) - before}",
            "print('\\n'.join(sorted(top - set(sys.stdlib_module_names) - set(sys.builtin_module_names))))",
        ]
    )

    result = run_python("-c", code)

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["agent_runtime"]


def test_the_entry_points_parse_on_old_interpreters() -> None:
    """__main__ checks the version before importing the rest, so it must itself parse there.

    __init__ too: importing __main__ from the package imports it first.
    """
    for name in ("__init__.py", "__main__.py"):
        ast.parse((RUNTIME_SOURCE / name).read_text(), feature_version=(3, 6))


def test_no_command_prints_the_usage(built_kit: Path) -> None:
    result = run_python(str(paths.runtime_pyz(built_kit)))

    assert result.returncode == 2
    assert "usage: agent_runtime" in result.stderr


def test_root_mode_is_given_the_kit_alone(built_kit: Path) -> None:
    """As session-init runs it through sudo: AGENT_KIT_DIR preserved, the other session variables gone.

    Run only as far as its refusal: SUDO_USER is never the sandbox's agent here.
    """
    result = subprocess.run(
        runtime_command(built_kit, "harden"),
        env={"PATH": os.environ["PATH"], contract.KIT_DIR: str(built_kit), "SUDO_USER": "will"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "only runs inside a foundry sandbox" in result.stderr
