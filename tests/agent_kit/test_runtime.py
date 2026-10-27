"""The built agent runtime, run as the kit's hooks and the launcher run it: ``python -IS <pyz> ...``."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_runtime import contract
from agent_runtime.agent_kit import PYTHON_FLAGS, RUNTIME_PYZ, AgentKit
from tests.support.kit import runtime_command

RUNTIME_SOURCE = Path(__file__).parents[2] / "src" / "agent_runtime"


def run_python(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, PYTHON_FLAGS, *args], capture_output=True, text=True, check=False)


def test_the_runtime_imports_only_the_standard_library(built_kit: Path) -> None:
    """Every module of the package, imported from the zipapp, loads nothing outside the standard library: neither
    foundry nor yaml, nor anything else installed, has to be in the sandbox. (What the interpreter's own site
    loads before, a virtualenv's for one, isn't the runtime's.)"""
    pyz = AgentKit(built_kit).runtime
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
    result = run_python(str(AgentKit(built_kit).runtime))

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


def test_root_mode_without_the_kit_names_it(built_kit: Path) -> None:
    """Root mode is given AGENT_KIT_DIR alone; without it, it says so, as every command does, and changes nothing."""
    result = subprocess.run(
        runtime_command(built_kit, "harden"),
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr == (
        "agent_runtime harden: AGENT_KIT_DIR not set; this runs inside a foundry sandbox, which sets them\n"
    )


# --- every command a sandbox runs, outside one --------------------------------------

RUNTIME = ("<python>", PYTHON_FLAGS, f"<kit>/{RUNTIME_PYZ}")


@pytest.mark.parametrize(
    "command",
    [
        (*RUNTIME, "git-hook", "pre-commit"),
        (*RUNTIME, "git-hook", "pre-push"),
        (*RUNTIME, "git-hook", "prepare-commit-msg", "<kit>/message"),
        (*RUNTIME, "claude-hook", "session-check"),
        (*RUNTIME, "session-init"),
        (*RUNTIME, "session-setup"),
        (*RUNTIME, "task", "show"),
    ],
)
def test_a_command_run_outside_a_sandbox_names_the_variable_it_lacks(built_kit, command: tuple[str, ...]) -> None:
    argv = [arg.replace("<kit>", str(built_kit)).replace("<python>", sys.executable) for arg in command]
    result = subprocess.run(
        argv, env={"PATH": os.environ["PATH"]}, input="", capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert "AGENT_" in result.stderr and "not set" in result.stderr


def test_a_hook_without_the_session_variables_names_itself(built_kit: Path) -> None:
    """As every other command does: the hook's own name, not the `claude-hook` command's."""
    result = subprocess.run(
        runtime_command(built_kit, "claude-hook", "session-check"),
        env={"PATH": os.environ["PATH"]},
        input="",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr == (
        f"agent_runtime session-check: {', '.join(contract.NAMES)} not set; "
        "this runs inside a foundry sandbox, which sets them\n"
    )
