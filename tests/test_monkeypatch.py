"""monkeypatch stays inside ProcessEnvironment, so every change a test makes to its process is one of the kinds
ProcessEnvironment offers."""

import ast
from pathlib import Path

from tests.support import REPOSITORY

MONKEYPATCH_NAMES = {"monkeypatch", "MonkeyPatch"}

ALLOWED_DEFINITION_BY_FILE = {
    Path("tests/support/__init__.py"): "ProcessEnvironment",
    Path("tests/conftest.py"): "process_environment",
}
"""The one class and the one fixture that may name monkeypatch, by the file that defines each."""


def monkeypatch_lines(tree: ast.AST) -> list[int]:
    """The lines in ``tree`` that name pytest's monkeypatch: as a parameter, a variable, an attribute or an import."""
    lines = set()
    for node in ast.walk(tree):
        match node:
            case ast.arg(arg=name) | ast.Name(id=name) | ast.Attribute(attr=name) if name in MONKEYPATCH_NAMES:
                lines.add(node.lineno)
            case ast.alias(name=name) if name.rsplit(".", 1)[-1] in MONKEYPATCH_NAMES:
                lines.add(node.lineno)
    return sorted(lines)


def test_only_process_environment_uses_monkeypatch() -> None:
    """A new reason to change the process is a new ProcessEnvironment method, reviewed like any other change."""
    uses = []
    for path in sorted((REPOSITORY / "tests").rglob("*.py")):
        relative_path = path.relative_to(REPOSITORY)
        allowed_definition = ALLOWED_DEFINITION_BY_FILE.get(relative_path)
        for statement in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(statement, (ast.FunctionDef, ast.ClassDef)) and statement.name == allowed_definition:
                continue
            uses += [f"{relative_path}:{line}" for line in monkeypatch_lines(statement)]
    assert uses == [], f"use ProcessEnvironment, or add the method you need to it: {', '.join(uses)}"


def test_each_way_of_naming_monkeypatch_is_found_and_a_string_is_not() -> None:
    """The check itself, on the shapes it is for."""
    source = (
        "def f(monkeypatch): pass\n"
        "patch = pytest.MonkeyPatch()\n"
        "from _pytest.monkeypatch import MonkeyPatch\n"
        "monkeypatch.setenv('A', 'b')\n"
        "note = 'monkeypatch'\n"
    )
    assert monkeypatch_lines(ast.parse(source)) == [1, 2, 3, 4]
