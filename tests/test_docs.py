"""The docs stay true to the code: their links and anchors resolve, the paths they name exist, the README
sections messages point to exist, and the command tables list exactly the commands the parsers define.

A rename that strands a doc fails here, in the pull request that made it.
"""

import argparse
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent_runtime import __main__ as runtime_main
from foundry import cli

REPOSITORY = Path(__file__).parents[1]
SKIPPED = ("agent-kit/", "config/task-template/", ".venv/", "tests/")
"""What isn't the foundry's documentation: what agents are given, task templates, and test fixtures."""
DOCS = sorted(
    path
    for path in REPOSITORY.rglob("*.md")
    if not str(path.relative_to(REPOSITORY)).startswith(SKIPPED) and ".git" not in path.parts
)
NAMED_PATH = re.compile(r"`((?:src|tests|config|agent-kit|docs)/[^`\s]*)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def anchors(markdown: str) -> set[str]:
    """The anchors GitHub gives a file's headings: lowercase, punctuation dropped, spaces as hyphens."""
    headings = re.findall(r"^#+ (.+)$", markdown, re.MULTILINE)
    return {re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-") for heading in headings}


def links(doc: Path) -> Iterator[str]:
    for target in LINK.findall(doc.read_text()):
        if not target.startswith(("http://", "https://", "mailto:")):
            yield target


@pytest.fixture(params=DOCS, ids=lambda doc: str(doc.relative_to(REPOSITORY)))
def doc(request: pytest.FixtureRequest) -> Path:
    path: Path = request.param
    return path


def test_the_docs_are_found() -> None:
    assert REPOSITORY / "README.md" in DOCS and REPOSITORY / "docs" / "adr" / "README.md" in DOCS


def test_every_link_and_anchor_resolves(doc: Path) -> None:
    for target in links(doc):
        file_part, _, anchor = target.partition("#")
        linked = (doc.parent / file_part).resolve() if file_part else doc
        assert linked.exists(), f"{target}: no such file"
        if anchor:
            assert anchor in anchors(linked.read_text()), f"{target}: no such heading in {linked.name}"


def test_every_path_named_exists(doc: Path) -> None:
    """Placeholders (`<role>`), globs and the untracked build are not paths to check."""
    for named in NAMED_PATH.findall(doc.read_text()):
        if any(mark in named for mark in "<*…") or ".build" in named:
            continue
        assert (REPOSITORY / named.rstrip(":,.")).exists(), f"{named}: no such path"


def test_the_readme_sections_messages_point_to_exist() -> None:
    sources = [*REPOSITORY.joinpath("src").rglob("*.py")]
    pointed = {
        section
        for source in sources
        for section in re.findall(r"see ([A-Z][\w ]+?) in the (?:foundry's )?README", source.read_text())
    }
    assert pointed, "no message points into the README any more; drop this test"
    readme = (REPOSITORY / "README.md").read_text()
    assert {section for section in pointed if f"## {section}\n" not in readme} == set()


def subcommands(parser: argparse.ArgumentParser) -> set[str]:
    """Every runnable command under ``parser``, as words: a subcommand, then any argument it limits to choices."""
    found: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                found |= {f"{name} {sub}" for sub in subcommands(child)} or {name}
        elif action.choices and not action.option_strings:
            found |= {str(choice) for choice in action.choices}
    return found


def table_commands(markdown: str, program: str = "") -> set[str]:
    """The commands named in tables' first columns, each up to its first argument; with ``program``, only the
    ones it starts, without it."""
    commands = set()
    for row in markdown.splitlines():
        if not row.startswith("| `"):
            continue
        for cell in re.findall(r"`([^`]+)`", row.split("|")[1]):
            words = cell.split()
            if program:
                if words[0] != program:
                    continue
                words = words[1:]
            if command := " ".join(word for word in words if re.fullmatch(r"[a-z][a-z-]*", word)):
                commands.add(command)
    return commands


def test_the_readme_lists_exactly_foundrys_commands() -> None:
    readme = (REPOSITORY / "README.md").read_text()
    assert table_commands(readme, "foundry") == subcommands(cli.build_parser())


def test_the_architecture_lists_exactly_the_runtimes_commands() -> None:
    runtime = subcommands(runtime_main.build_parser())
    first_words = {command.split()[0] for command in runtime}
    architecture = (REPOSITORY / "ARCHITECTURE.md").read_text()
    assert {command for command in table_commands(architecture) if command.split()[0] in first_words} == runtime
