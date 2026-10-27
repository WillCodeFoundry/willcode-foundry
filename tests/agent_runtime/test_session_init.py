"""session_init's order, in-process: set up, harden as root while sudo works, then check, on one temporary machine.

Root mode is reached through ``run_as_root``: here it calls harden in-process with the machine's root view,
where the real launch goes through sudo. tests/agent_kit/test_session_init.py checks that hand-over itself.
"""

from pathlib import Path

import pytest

from agent_runtime import hardening, session_init
from agent_runtime.session_setup import SetupError
from tests.support import SessionFor
from tests.support.machine import SUDO_USER, TemporaryMachine


def in_process_root(machine: TemporaryMachine, calls: list[Path], exit_code: int = 0) -> session_init.RunAsRoot:
    """Root mode, run here as root's view of the machine; records the kit it was given."""

    def run_as_root(_: hardening.Machine, agent_kit_dir: Path) -> int:
        calls.append(agent_kit_dir)
        if exit_code == 0:
            hardening.harden(agent_kit_dir, SUDO_USER, machine.root_mode)
        return exit_code

    return run_as_root


def test_a_first_launch_sets_up_hardens_as_root_then_verifies(
    session_for: SessionFor,
    created_task: Path,
    machine: TemporaryMachine,
    read_only_kit: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[Path] = []

    returncode = session_init.session_init(
        session_for(read_only_kit, created_task), machine.agent_mode, in_process_root(machine, calls)
    )

    assert returncode == 0, capsys.readouterr().err
    assert calls == [read_only_kit]
    out = capsys.readouterr().out
    assert out.index("session-setup: checkouts ready") < out.index("check-hardening: hardened")


def test_a_relaunch_only_verifies(
    session_for: SessionFor,
    created_task: Path,
    machine: TemporaryMachine,
    read_only_kit: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Root mode left sudo mode 0: it can't execute, which counts as no sudo, so root mode doesn't run again."""
    calls: list[Path] = []
    session = session_for(read_only_kit, created_task)
    session_init.session_init(session, machine.agent_mode, in_process_root(machine, calls))

    assert session_init.session_init(session, machine.agent_mode, in_process_root(machine, calls)) == 0
    assert calls == [read_only_kit]
    assert capsys.readouterr().out.endswith("check-hardening: hardened\n")


def test_a_failing_root_mode_stops_the_launch_before_the_check(
    session_for: SessionFor,
    created_task: Path,
    machine: TemporaryMachine,
    read_only_kit: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[Path] = []

    returncode = session_init.session_init(
        session_for(read_only_kit, created_task), machine.agent_mode, in_process_root(machine, calls, exit_code=3)
    )

    assert returncode == 3
    assert "check-hardening:" not in capsys.readouterr().out


def test_a_failing_setup_stops_the_launch_before_root(
    session_for: SessionFor, created_task: Path, machine: TemporaryMachine, tmp_path: Path
) -> None:
    calls: list[Path] = []
    no_roles = tmp_path / "kit-without-roles"
    no_roles.mkdir()

    with pytest.raises(SetupError, match=r"^session-setup: role 'dev': .* has no ROLE.md or gitconfig$"):
        session_init.session_init(
            session_for(no_roles, created_task), machine.agent_mode, in_process_root(machine, calls)
        )
    assert calls == []


def test_an_unhardened_machine_is_refused_naming_what_the_agent_can_still_do(
    session_for: SessionFor,
    created_task: Path,
    machine: TemporaryMachine,
    read_only_kit: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Root mode ran, but the agent can still write the settings: the check stops the launch."""
    session_init.session_init(
        session_for(read_only_kit, created_task), machine.agent_mode, in_process_root(machine, [])
    )
    machine.root_mode.managed_settings.chmod(0o646)

    assert (
        session_init.session_init(
            session_for(read_only_kit, created_task), machine.agent_mode, in_process_root(machine, [])
        )
        == 1
    )
    assert capsys.readouterr().err == (
        "check-hardening: not starting the agent; it can still:\n"
        f"  change Claude's managed settings: {machine.root_mode.managed_settings} is writable\n"
        "This sandbox needs recreating: see Recreating a sandbox in the foundry's README.\n"
    )
