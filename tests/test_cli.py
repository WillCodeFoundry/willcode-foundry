"""foundry's entry point shows progress on stderr, and detail too with -v."""

import logging

import pytest

from foundry import cli

_LOGGER = logging.getLogger("foundry.test_cli")


@pytest.mark.parametrize(("verbose", "stderr"), [(False, "==> step\n"), (True, "==> step\n==> detail\n")])
def test_progress_shows_on_stderr_and_detail_only_when_verbose(
    verbose: bool, stderr: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with cli.progress_on_stderr(verbose=verbose):
        _LOGGER.info("step")
        _LOGGER.debug("detail")

    assert capsys.readouterr() == ("", stderr)


def test_nothing_is_left_on_the_logger_even_when_the_command_fails() -> None:
    foundry_logger = logging.getLogger("foundry")
    before = (foundry_logger.level, list(foundry_logger.handlers))

    with pytest.raises(RuntimeError), cli.progress_on_stderr(verbose=True):
        raise RuntimeError

    assert (foundry_logger.level, foundry_logger.handlers) == before


@pytest.mark.parametrize(("argv", "verbose"), [(["prune"], False), (["-v", "prune"], True)])
def test_v_asks_for_the_detail(argv: list[str], verbose: bool) -> None:
    assert cli.build_parser().parse_args(argv).verbose is verbose
