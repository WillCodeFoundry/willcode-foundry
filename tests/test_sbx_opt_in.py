"""The sbx tier launches a real sandbox and removes it with `sbx env rm --force` in this foundry, so it runs
only when -m asks for it, never because another -m replaced the default deselection."""

import pytest

from tests.support import run_pytest


def collected(*options: str) -> list[str]:
    """The tests a run with ``options`` would select, by id: the repository's addopts has -q."""
    return [line for line in run_pytest("--collect-only", *options, "tests/sbx").stdout.splitlines() if "::" in line]


@pytest.mark.parametrize(
    "options", [(), ("-m", "not docker"), ("-m", "not sbx or sbx and docker"), ("-o", "addopts=", "-q")]
)
def test_the_sbx_tier_isnt_selected_unless_named(options: tuple[str, ...]) -> None:
    assert collected(*options) == []


@pytest.mark.parametrize("expression", ["sbx", "sbx or docker"])
def test_the_sbx_tier_runs_when_named(expression: str) -> None:
    assert collected("-m", expression)
