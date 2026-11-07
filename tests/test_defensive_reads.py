"""Design rule 6, where a tool can see it: no getattr or hasattr with a literal attribute name in src.

A literal name means the code knows the attribute, so it reads it and lets the type checker hold it. A default
hides a renamed or missing attribute. Ruff's B009 catches getattr without a default, not with one."""

import ast
from pathlib import Path

REPOSITORY = Path(__file__).parents[1]


def defensive_read_lines(source: str) -> list[int]:
    """The lines of ``source`` holding a getattr or hasattr call whose attribute name is a string literal."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"getattr", "hasattr"}
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ]


def test_src_reads_known_attributes_directly() -> None:
    found = [
        f"{path.relative_to(REPOSITORY)}:{line}"
        for path in sorted((REPOSITORY / "src").rglob("*.py"))
        for line in defensive_read_lines(path.read_text())
    ]
    assert found == []


def test_a_literal_name_is_found_and_a_variable_one_is_not() -> None:
    """The check itself, on the shape it is for."""
    assert defensive_read_lines('token = getattr(user, "token", None)\nok = hasattr(user, name)\n') == [1]
