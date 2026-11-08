"""foundry's entry point shows progress on stderr, and detail too with -v."""

import argparse
import logging

import pytest

from foundry import cli

_LOGGER = logging.getLogger("foundry.test_cli")


class Steps:
    """A command that shows one progress line and one line of detail, then succeeds."""

    @staticmethod
    def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
        subparsers.add_parser("steps").set_defaults(func=Steps.main)

    @staticmethod
    def main(args: argparse.Namespace) -> int:
        _LOGGER.info("step")
        _LOGGER.debug("detail")
        return 0


@pytest.mark.parametrize(("argv", "stderr"), [(["steps"], "==> step\n"), (["-v", "steps"], "==> step\n==> detail\n")])
def test_progress_shows_on_stderr_and_detail_only_with_v(
    argv: list[str], stderr: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "COMMANDS", (Steps,))

    assert cli.main(argv) == 0
    assert capsys.readouterr() == ("", stderr)


def test_nothing_is_left_on_the_logger_after_a_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "COMMANDS", (Steps,))
    foundry_logger = logging.getLogger("foundry")
    before = (foundry_logger.level, list(foundry_logger.handlers))

    cli.main(["-v", "steps"])

    assert (foundry_logger.level, foundry_logger.handlers) == before
