"""agent-kit/hooks/: one stub per git hook, each finding the runtime from its own path.

The stubs must find the pyz before they can import anything, so each spells out its path; these tests hold
that path to agent_kit.RUNTIME_PYZ, and the stubs to one another.
"""

import re
from pathlib import Path, PurePosixPath

import pytest

from agent_runtime import contract, git_hooks
from agent_runtime.agent_kit import RUNTIME_PYZ

HOOKS_DIR = Path(__file__).parents[2] / "agent-kit" / "hooks"
STUBS = sorted(HOOKS_DIR.iterdir())


def test_there_is_a_stub_for_each_git_hook_the_runtime_has() -> None:
    assert [stub.name for stub in STUBS] == ["pre-commit", "pre-push", "prepare-commit-msg"]
    for stub in STUBS:
        assert callable(getattr(git_hooks, stub.name.replace("-", "_")))


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.name)
def test_a_stub_finds_the_runtime_where_the_build_puts_it(stub: Path) -> None:
    """``parent.parent`` is the kit; the parts after it are the runtime's path in the kit."""
    match = re.search(
        r'^RUNTIME = Path\(__file__\)\.resolve\(\)\.parent\.parent((?: / "[^"]+")+)$', stub.read_text(), re.M
    )

    assert match is not None
    assert PurePosixPath(*re.findall(r'"([^"]+)"', match.group(1))) == RUNTIME_PYZ


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.name)
def test_a_stub_runs_on_the_template_interpreter_with_the_runtimes_flags(stub: Path) -> None:
    assert stub.read_text().splitlines()[0] == f"#!{contract.PYTHON} {contract.PYTHON_FLAGS}"


def test_the_stubs_differ_only_in_their_hook() -> None:
    def generic(stub: Path) -> str:
        return stub.read_text().replace(stub.name, "<hook>").replace(stub.name.replace("-", "_"), "<function>")

    assert len({generic(stub) for stub in STUBS}) == 1
