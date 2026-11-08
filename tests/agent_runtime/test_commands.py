"""What the runtime's commands print for each outcome the library returns, in-process.

The outcomes themselves are tested beside their modules, such as tests/agent_runtime/test_session_init.py.
tests/agent_kit/ runs each command once, as delivered.
"""

import logging

import pytest

from agent_runtime import session_init
from agent_runtime.commands import check_hardening, progress_on_stdout
from agent_runtime.commands import session_init as session_init_command

CAN_STILL = ["change Claude's managed settings: /etc/claude-code/managed-settings.json is writable"]


def test_a_hardened_sandbox_is_reported_on_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_hardening.report([]) == 0

    assert capsys.readouterr() == ("check-hardening: hardened\n", "")


def test_what_the_agent_can_still_do_stops_the_launch_and_says_how_to_recover(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert check_hardening.report(CAN_STILL) == 1

    assert capsys.readouterr() == (
        "",
        "check-hardening: not starting the agent; it can still:\n"
        f"  {CAN_STILL[0]}\n"
        "This sandbox needs recreating: see Recreating a sandbox in the foundry's README.\n",
    )


def test_session_init_reports_the_check_it_ran(capsys: pytest.CaptureFixture[str]) -> None:
    assert session_init_command.report(session_init.Checked(can_still=CAN_STILL)) == 1

    assert "it can still:" in capsys.readouterr().err


def test_a_failed_root_mode_passes_on_its_exit_code_without_a_word(capsys: pytest.CaptureFixture[str]) -> None:
    """Root mode has already said why, on the terminal sudo gave it."""
    assert session_init_command.report(session_init.RootModeFailed(exit_code=3)) == 3

    assert capsys.readouterr() == ("", "")


def test_progress_is_shown_on_stdout_only_while_a_command_runs(capsys: pytest.CaptureFixture[str]) -> None:
    logger = logging.getLogger("agent_runtime.session_setup")

    with progress_on_stdout():
        logger.info("session-setup: checkouts ready")
    logger.info("after the command")

    assert capsys.readouterr().out == "session-setup: checkouts ready\n"
