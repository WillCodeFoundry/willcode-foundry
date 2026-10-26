"""The runtime's session-setup, the agent user's part of session-init, run from the built kit against a local origin.

It never needs root, so it runs here as in a sandbox, with a sandbox's variables and a throwaway HOME.
"""

import os
import shutil
import subprocess
from pathlib import Path

from foundry.task import NOTES_BRANCH
from tests.agent_kit.conftest import TASK, git, runtime_command


def session_setup(kit_env: dict[str, str], origin: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **kit_env, "AGENT_REPO_URL": f"file://{origin}"}
    return subprocess.run(
        runtime_command(Path(env["AGENT_KIT_DIR"]), "session-setup"),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_task_without_its_branches_is_explained(kit_env, origin) -> None:
    result = session_setup(kit_env(TASK), origin)
    assert result.returncode == 1
    assert f"task {TASK.id} has not been created" in result.stderr
    assert f"branch {TASK.branch}" in result.stderr and f"branch {NOTES_BRANCH}" in result.stderr


def test_a_task_without_its_task_md_is_explained(tmp_path, kit_env, origin) -> None:
    seed = tmp_path / "seed"
    git(seed, "push", "-q", "origin", f"HEAD:refs/heads/{TASK.branch}")
    git(seed, "switch", "-q", "--orphan", NOTES_BRANCH)
    (seed / "x").write_text("x\n")
    git(seed, "add", "x")
    git(seed, "commit", "-qm", "notes")
    git(seed, "push", "-q", "origin", NOTES_BRANCH)

    result = session_setup(kit_env(TASK), origin)
    assert result.returncode == 1
    assert f"{NOTES_BRANCH} has no {TASK.task_file}" in result.stderr
    assert not (tmp_path / "home" / ".claude").exists()  # stopped before writing instructions


def git_out(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def test_a_created_task_gets_both_checkouts_with_the_kits_hooks(built_kit, kit_env, created_task) -> None:
    env = kit_env(TASK)

    result = session_setup(env, created_task)

    assert result.returncode == 0, result.stderr
    code, notes = Path(env["AGENT_PROJECT_DIR"]), Path(env["AGENT_NOTES_DIR"])
    assert git_out(code, "branch", "--show-current") == TASK.branch
    assert git_out(notes, "branch", "--show-current") == NOTES_BRANCH
    assert (notes / TASK.task_file).read_text() == "# Task\n"
    assert git_out(code, "config", "core.hooksPath") == str(built_kit / "hooks")


def test_the_git_identity_is_the_roles(tmp_path, built_kit, kit_env, created_task) -> None:
    assert session_setup(kit_env(TASK), created_task).returncode == 0

    assert git_out(tmp_path, "config", "--global", "include.path") == str(built_kit / "roles" / "dev" / "gitconfig")
    assert git_out(tmp_path, "config", "--global", "gpg.ssh.allowedSignersFile") == str(
        built_kit / "git" / "allowed_signers"
    )
    assert git_out(tmp_path, "config", "user.name") == "wc-foundry-dev"


def test_the_agent_starts_briefed_with_its_roles_skills(tmp_path, built_kit, kit_env, created_task) -> None:
    env = kit_env(TASK)

    assert session_setup(env, created_task).returncode == 0

    claude_dir = tmp_path / "home" / ".claude"
    imports = [line for line in (claude_dir / "CLAUDE.md").read_text().splitlines() if line.startswith("@")]
    assert imports == [
        f"@{built_kit / 'AGENTS.md'}",
        f"@{built_kit / 'roles' / 'dev' / 'ROLE.md'}",
        f"@{Path(env['AGENT_NOTES_DIR']) / TASK.task_file}",
    ]
    assert (claude_dir / "skills").readlink() == built_kit / "roles" / "dev" / "skills"


def test_a_second_run_succeeds_and_changes_nothing(tmp_path, kit_env, created_task) -> None:
    env = kit_env(TASK)
    assert session_setup(env, created_task).returncode == 0
    code = Path(env["AGENT_PROJECT_DIR"])
    before = (git_out(code, "rev-parse", "HEAD"), (tmp_path / "home" / ".claude" / "CLAUDE.md").read_text())

    result = session_setup(env, created_task)

    assert result.returncode == 0, result.stderr
    assert (git_out(code, "rev-parse", "HEAD"), (tmp_path / "home" / ".claude" / "CLAUDE.md").read_text()) == before
    assert git_out(code, "branch", "--show-current") == TASK.branch


def test_a_role_that_signs_without_a_key_is_refused(tmp_path, built_kit, kit_env, created_task) -> None:
    kit = tmp_path / "agent-kit"
    shutil.copytree(built_kit, kit, symlinks=True)
    gitconfig = kit / "roles" / "dev" / "gitconfig"
    gitconfig.write_text("".join(line for line in gitconfig.read_text().splitlines(True) if "signingkey" not in line))

    result = session_setup({**kit_env(TASK), "AGENT_KIT_DIR": str(kit)}, created_task)

    assert result.returncode == 1
    assert "dev signs commits but" in result.stderr and "sets no user.signingkey" in result.stderr


def test_a_skills_folder_in_place_of_the_link_is_refused(tmp_path, kit_env, created_task) -> None:
    (tmp_path / "home" / ".claude" / "skills").mkdir(parents=True)

    result = session_setup(kit_env(TASK), created_task)

    assert result.returncode == 1
    assert "is a folder, not the link to the role's skills" in result.stderr
