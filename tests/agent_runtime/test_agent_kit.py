"""agent_runtime.agent_kit: where things sit in the agent kit, spelled out once more here as literals, and
the rule for what a role's folder must hold, and how the runtime in it is called."""

import subprocess
import sys
from pathlib import Path, PurePosixPath

from agent_runtime.agent_kit import PYTHON_FLAGS, RUNTIME_PYZ, AgentKit
from foundry import yaml_io

REPO_ROOT = Path(__file__).parents[2]
SOURCE_KIT = AgentKit(REPO_ROOT / "agent-kit")


def test_the_kits_paths() -> None:
    kit = AgentKit(Path("/kit"))

    assert RUNTIME_PYZ == PurePosixPath(".build/agent_runtime.pyz")
    assert kit.runtime == Path("/kit/.build/agent_runtime.pyz")
    assert kit.managed_settings == Path("/kit/claude/managed-settings.json")
    assert kit.hooks == Path("/kit/hooks")
    assert kit.allowed_signers == Path("/kit/git/allowed_signers")
    assert kit.agents_md == Path("/kit/AGENTS.md")
    assert kit.skills == Path("/kit/skills")


def test_a_roles_paths() -> None:
    role = AgentKit(Path("/kit")).role("dev")

    assert role.dir == Path("/kit/roles/dev")
    assert role.role_md == Path("/kit/roles/dev/ROLE.md")
    assert role.gitconfig == Path("/kit/roles/dev/gitconfig")
    assert role.skills == Path("/kit/roles/dev/skills")


def test_a_role_folder_names_the_files_it_lacks_in_order(tmp_path: Path) -> None:
    role = AgentKit(tmp_path).role("dev")
    assert role.missing() == ["ROLE.md", "gitconfig"]  # no folder at all

    role.dir.mkdir(parents=True)
    (role.dir / "gitconfig").write_text("")
    assert role.missing() == ["ROLE.md"]

    (role.dir / "ROLE.md").write_text("")
    (role.dir / "gitconfig").unlink()
    assert role.missing() == ["gitconfig"]

    (role.dir / "gitconfig").write_text("")
    assert role.missing() == []


def test_a_folder_where_a_file_should_be_is_missing(tmp_path: Path) -> None:
    role = AgentKit(tmp_path).role("dev")
    (role.dir / "ROLE.md").mkdir(parents=True)
    (role.dir / "gitconfig").write_text("")

    assert role.missing() == ["ROLE.md"]


def test_the_real_kit_has_every_path_the_module_names(built_kit: Path) -> None:
    """The runtime only once built; everything else as checked in."""
    assert AgentKit(built_kit).runtime.is_file()
    assert SOURCE_KIT.managed_settings.is_file()
    assert SOURCE_KIT.hooks.is_dir()
    assert SOURCE_KIT.allowed_signers.is_file()
    assert SOURCE_KIT.agents_md.is_file()
    assert SOURCE_KIT.skills.is_dir()


def test_every_configured_role_lacks_nothing() -> None:
    roles = yaml_io.load(REPO_ROOT / "config" / "foundry.yaml")["roles"]

    assert roles
    assert {name: SOURCE_KIT.role(name).missing() for name in roles} == {name: [] for name in roles}


def test_a_command_runs_the_kits_runtime_isolated() -> None:
    assert AgentKit(Path("/kit")).command("hook", "guard-bash") == (
        "/usr/bin/python3",
        "-IS",
        "/kit/.build/agent_runtime.pyz",
        "hook",
        "guard-bash",
    )


def test_the_flags_isolate_the_runtime_and_skip_site() -> None:
    """-I ignores PYTHON* variables and user site-packages, and -S skips site, so no .pth file in any
    site-packages runs. One argument, as a shebang line passes."""
    flags = subprocess.run(
        [sys.executable, PYTHON_FLAGS, "-c", "import sys; print(sys.flags.isolated, sys.flags.no_site)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert flags.stdout == "1 1\n"
