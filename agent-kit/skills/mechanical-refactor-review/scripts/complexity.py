#!/usr/bin/env python3
"""Rank Python functions by rough complexity, to decide where to read first.

Usage: complexity.py PATH [PATH ...] [--top N]

Each PATH may be a file or a directory. A directory is searched for *.py
files, and for extensionless files whose first line is a python shebang,
such as hook scripts. For each function the script prints:

  branches  1 + decision points: if, for, while, conditional expression,
            except clause, comprehension, match case, and each extra
            operand of `and`/`or` (an approximation of cyclomatic complexity)
  depth     deepest nesting of if/for/while/try/with/match inside the function
  lines     length of the function

A nested function's decision points are counted both in itself and in the
function that contains it. That is good enough for choosing where to look
first, which is all this is for: it is not a finding in itself.
Requires Python 3.10+.
"""

import argparse
import ast
import sys
from pathlib import Path

DECISIONS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.IfExp,
    ast.ExceptHandler,
    ast.comprehension,
    ast.match_case,
)
NESTING = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Match,
)


def python_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    found = []
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_file() or "__pycache__" in candidate.parts:
            continue
        if candidate.suffix == ".py":
            found.append(candidate)
        elif not candidate.suffix:
            try:
                with candidate.open(encoding="utf-8") as file:
                    first_line = file.readline()
            except (UnicodeDecodeError, OSError):
                continue
            if first_line.startswith("#!") and "python" in first_line:
                found.append(candidate)
    return found


def nesting_depth(node: ast.AST, level: int = 0) -> int:
    deepest = level
    for child in ast.iter_child_nodes(node):
        deepest = max(
            deepest,
            nesting_depth(child, level + 1 if isinstance(child, NESTING) else level),
        )
    return deepest


def measure(file_path: Path) -> list[tuple[int, int, int, str]]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as error:
        print(f"skipped {file_path}: {error}", file=sys.stderr)
        return []
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            inner = list(ast.walk(node))
            branches = 1 + sum(isinstance(n, DECISIONS) for n in inner)
            branches += sum(len(n.values) - 1 for n in inner if isinstance(n, ast.BoolOp))
            lines = (node.end_lineno or node.lineno) - node.lineno + 1
            rows.append(
                (
                    branches,
                    nesting_depth(node),
                    lines,
                    f"{file_path}:{node.lineno} {node.name}",
                )
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank Python functions by rough complexity.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    rows = [row for path in args.paths for file_path in python_files(path) for row in measure(file_path)]
    print(f"{'branches':>8} {'depth':>5} {'lines':>5}  function")
    for branches, depth, lines, where in sorted(rows, reverse=True)[: args.top]:
        print(f"{branches:>8} {depth:>5} {lines:>5}  {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
