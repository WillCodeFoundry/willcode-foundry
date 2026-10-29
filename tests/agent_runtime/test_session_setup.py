"""session_setup, in-process, against a local origin, with a throwaway HOME: the rules of setting a sandbox up.

tests/agent_kit/test_session_setup.py runs it once through the built pyz.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from agent_runtime import contract, session_setup
from agent_runtime.session_setup import SetupError
from foundry.task import NOTES_BRANCH
from tests.support import TASK, SessionFor, git


@pytest.fixture
def home(tmp_path: Path, git_identity: Path) -> Path:
    """The HOME git_identity set up: where the global git config and ~/.claude go."""
    return git_identity


def test_a_created_task_gets_both_checkouts(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path
) -> None:
    session = session_for(built_kit, created_task)

    session_setup.session_setup(session, home)

    code, notes = session.agent_project_dir, session.agent_notes_dir
    assert git(code, "branch", "--show-current").stdout.strip() == TASK.branch
    assert git(notes, "branch", "--show-current").stdout.strip() == NOTES_BRANCH
    assert (notes / TASK.task_file).read_text() == "# Task\n"
    assert git(code, "config", "core.hooksPath").stdout.strip() == str(built_kit / "hooks")


def test_a_task_without_its_branches_is_explained(
    session_for: SessionFor, built_kit: Path, origin: Path, home: Path
) -> None:
    with pytest.raises(SetupError) as refused:
        session_setup.session_setup(session_for(built_kit, origin), home)

    assert f"task {TASK.id} has not been created" in str(refused.value)
    assert f"branch {TASK.branch}" in str(refused.value) and f"branch {NOTES_BRANCH}" in str(refused.value)


def test_a_task_without_its_task_md_is_explained(
    session_for: SessionFor, built_kit: Path, origin: Path, tmp_path: Path, home: Path
) -> None:
    seed = tmp_path / "seed"
    git(seed, "push", "-q", "origin", f"HEAD:refs/heads/{TASK.branch}")
    git(seed, "switch", "-q", "--orphan", NOTES_BRANCH)
    (seed / "x").write_text("x\n")
    git(seed, "add", "x")
    git(seed, "commit", "-qm", "notes")
    git(seed, "push", "-q", "origin", NOTES_BRANCH)

    with pytest.raises(SetupError, match=rf"^session-setup: {NOTES_BRANCH} has no {TASK.task_file};"):
        session_setup.session_setup(session_for(built_kit, origin), home)
    assert not (home / ".claude").exists()  # stopped before writing instructions


def test_the_git_identity_is_the_roles(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path
) -> None:
    session_setup.session_setup(session_for(built_kit, created_task), home)

    assert git(home, "config", "--global", "include.path").stdout.strip() == str(
        built_kit / "roles" / "dev" / "gitconfig"
    )
    assert git(home, "config", "--global", "gpg.ssh.allowedSignersFile").stdout.strip() == str(
        built_kit / "git" / "allowed_signers"
    )
    assert git(home, "config", "user.name").stdout.strip() == "wc-foundry-dev"


def test_the_agent_starts_briefed_with_its_roles_skills(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path
) -> None:
    session = session_for(built_kit, created_task)

    session_setup.session_setup(session, home)

    imports = [line for line in (home / ".claude" / "CLAUDE.md").read_text().splitlines() if line.startswith("@")]
    assert imports == [
        f"@{built_kit / 'AGENTS.md'}",
        f"@{built_kit / 'roles' / 'dev' / 'ROLE.md'}",
        f"@{session.agent_notes_dir / TASK.task_file}",
    ]
    assert (home / ".claude" / "skills").readlink() == built_kit / "roles" / "dev" / "skills"


@pytest.mark.parametrize("name", ["CLAUDE.md", ".CLAUDE.md.partial"])
def test_a_link_in_or_beside_the_instructions_place_cant_catch_their_write(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path, name: str
) -> None:
    """~/.claude/CLAUDE.md is rewritten at every launch; a link the agent left there, or beside it, points
    elsewhere."""
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text("left alone\n")
    (home / ".claude").mkdir()
    (home / ".claude" / name).symlink_to(elsewhere)

    session_setup.session_setup(session_for(built_kit, created_task), home)

    assert elsewhere.read_text() == "left alone\n"
    assert not (home / ".claude" / "CLAUDE.md").is_symlink()
    assert "@" in (home / ".claude" / "CLAUDE.md").read_text()


def test_instructions_that_cant_be_written_are_a_setup_error(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path
) -> None:
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    claude_dir.chmod(0o555)
    try:
        with pytest.raises(SetupError) as refused:
            session_setup.session_setup(session_for(built_kit, created_task), home)
    finally:
        claude_dir.chmod(0o755)

    assert str(refused.value).startswith(
        f"session-setup: can't write the agent's instructions to {claude_dir / 'CLAUDE.md'}: "
    )


def test_a_second_run_succeeds_and_changes_nothing(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path
) -> None:
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    code = session.agent_project_dir
    before = (git(code, "rev-parse", "HEAD").stdout.strip(), (home / ".claude" / "CLAUDE.md").read_text())

    session_setup.session_setup(session, home)

    assert (git(code, "rev-parse", "HEAD").stdout.strip(), (home / ".claude" / "CLAUDE.md").read_text()) == before
    assert git(code, "branch", "--show-current").stdout.strip() == TASK.branch


def kit_copy(built_kit: Path, tmp_path: Path) -> Path:
    """A copy of the built kit a test may change."""
    kit = tmp_path / "agent-kit"
    shutil.copytree(built_kit, kit, symlinks=True)
    return kit


def test_a_role_that_signs_without_a_key_is_refused(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path
) -> None:
    kit = kit_copy(built_kit, tmp_path)
    gitconfig = kit / "roles" / "dev" / "gitconfig"
    gitconfig.write_text("".join(line for line in gitconfig.read_text().splitlines(True) if "signingkey" not in line))

    with pytest.raises(SetupError, match=r"dev signs commits but .* sets no user\.signingkey"):
        session_setup.session_setup(session_for(kit, created_task), home)


@pytest.mark.parametrize("make", ["folder", "file"])
def test_whatever_is_in_the_skills_place_is_replaced_by_the_link(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, make: str
) -> None:
    """sbx's Claude template ships ~/.claude/skills as a folder of the skills synced from an account."""
    skills = home / ".claude" / "skills"
    if make == "folder":
        synced_skill = skills / "synced" / "org_account" / "docx"
        synced_skill.mkdir(parents=True)
        (synced_skill / "SKILL.md").write_text("---\nname: docx\n---\n")
    else:
        skills.parent.mkdir(parents=True)
        skills.write_text("")

    session_setup.session_setup(session_for(built_kit, created_task), home)

    assert skills.readlink() == built_kit / "roles" / "dev" / "skills"


@pytest.mark.parametrize("removed", [["ROLE.md"], ["gitconfig"], ["ROLE.md", "gitconfig"]])
def test_a_role_folder_missing_a_required_file_is_refused_before_git(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path, removed: list[str]
) -> None:
    """Without gitconfig the agent has no identity; without ROLE.md it would start with no role, since a missing
    @ import is skipped without a word. Either stops setup before it changes anything."""
    kit = kit_copy(built_kit, tmp_path)
    role_dir = kit / "roles" / "dev"
    for name in removed:
        (role_dir / name).unlink()
    session = session_for(kit, created_task)

    with pytest.raises(SetupError) as refused:
        session_setup.session_setup(session, home)

    assert str(refused.value) == f"session-setup: role 'dev': {role_dir} has no {' or '.join(removed)}"
    included = subprocess.run(["git", "config", "--global", "--get", "include.path"], capture_output=True, check=False)
    assert included.returncode == 1  # the role's identity wasn't written
    assert not session.agent_project_dir.exists()  # nothing cloned


def test_a_failed_step_names_the_checkout_it_ran_in(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path
) -> None:
    """session-setup works in two checkouts: the message says which one to look at."""
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    shutil.rmtree(created_task)  # origin is gone: the next fetch fails

    with pytest.raises(SetupError) as refused:
        session_setup.session_setup(session, home)

    project = session.agent_project_dir
    assert str(refused.value) == f"session-setup: `git -C {project} fetch origin` failed; see git's message above"


def push_to_origin(origin: Path, tmp_path: Path, branch: str, files: dict[str, str], message: str = "more") -> None:
    """A commit on origin's ``branch`` adding or changing ``files``, as another role's push would."""
    other = tmp_path / f"other-{branch.replace('/', '-')}"
    if not other.exists():
        git(tmp_path, "clone", "-q", str(origin), str(other))
    git(other, "fetch", "-q", "origin")
    git(other, "checkout", "-q", "-B", branch, f"origin/{branch}")
    for name, text in files.items():
        (other / name).parent.mkdir(parents=True, exist_ok=True)
        (other / name).write_text(text)
    git(other, "add", ".")
    git(other, "commit", "-qm", message)
    git(other, "push", "-q", "origin", branch)


def tips(session: contract.Environ) -> tuple[str, str]:
    return (
        git(session.agent_project_dir, "rev-parse", "HEAD").stdout.strip(),
        git(session.agent_notes_dir, "rev-parse", "HEAD").stdout.strip(),
    )


def snapshot(session: contract.Environ) -> tuple[str, ...]:
    """Everything a refusal must leave alone: each checkout's HEAD, status, stashes and branch tips."""
    state = []
    for checkout in (session.agent_project_dir, session.agent_notes_dir):
        for args in (
            ("rev-parse", "HEAD"),
            ("status", "--porcelain"),
            ("stash", "list"),
            ("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"),
        ):
            state.append(git(checkout, *args).stdout)
    return tuple(state)


def test_a_relaunch_brings_both_checkouts_to_origins_tip(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path
) -> None:
    """The wcf-0025 bug: the dev was relaunched and read the notes as it had left them."""
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    push_to_origin(created_task, tmp_path, TASK.branch, {"new.py": "x\n"})
    push_to_origin(
        created_task,
        tmp_path,
        NOTES_BRANCH,
        {
            TASK.task_file: "# Task, edited\n",
            f"{TASK.task_notes_dir}/REVIEW.md": "review\n",
            f"{TASK.task_notes_dir}/TURN": "dev\n",
        },
    )

    session_setup.session_setup(session, home)

    code, notes = session.agent_project_dir, session.agent_notes_dir
    assert (code / "new.py").read_text() == "x\n"
    assert git(code, "rev-parse", "HEAD").stdout == git(code, "rev-parse", f"origin/{TASK.branch}").stdout
    assert git(notes, "rev-parse", "HEAD").stdout == git(notes, "rev-parse", f"origin/{NOTES_BRANCH}").stdout
    assert (notes / TASK.task_notes_dir / "REVIEW.md").read_text() == "review\n"
    assert (notes / TASK.task_file).read_text() == "# Task, edited\n"
    imports = [line for line in (home / ".claude" / "CLAUDE.md").read_text().splitlines() if line.startswith("@")]
    assert imports[-1] == f"@{notes / TASK.task_file}"


def test_the_notes_branch_is_brought_forward_when_only_its_directory_is_missing(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path
) -> None:
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    git(session.agent_project_dir, "worktree", "remove", str(session.agent_notes_dir))
    push_to_origin(created_task, tmp_path, NOTES_BRANCH, {f"{TASK.task_notes_dir}/TURN": "dev\n"})

    session_setup.session_setup(session, home)

    assert (session.agent_notes_dir / TASK.task_notes_dir / "TURN").read_text() == "dev\n"


def test_unpushed_commits_are_left_as_they_are(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path
) -> None:
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    for checkout in (session.agent_project_dir, session.agent_notes_dir):
        git(checkout, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "local")
    before = tips(session)

    session_setup.session_setup(session, home)

    assert tips(session) == before


def test_uncommitted_changes_that_dont_conflict_survive_the_update(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path
) -> None:
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    code, notes = session.agent_project_dir, session.agent_notes_dir
    (code / "README.md").write_text("edited\n")
    (notes / TASK.task_notes_dir / "PROGRESS.md").write_text("wip\n")
    push_to_origin(created_task, tmp_path, TASK.branch, {"new.py": "x\n"})
    push_to_origin(created_task, tmp_path, NOTES_BRANCH, {f"{TASK.task_notes_dir}/TURN": "dev\n"})

    session_setup.session_setup(session, home)

    assert (code / "new.py").is_file() and (code / "README.md").read_text() == "edited\n"
    assert (notes / TASK.task_notes_dir / "TURN").is_file()
    assert (notes / TASK.task_notes_dir / "PROGRESS.md").read_text() == "wip\n"


RECREATING = 'README\'s "Recreating a sandbox"'


def test_a_diverged_branch_is_refused_naming_the_local_commits(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path
) -> None:
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    code = session.agent_project_dir
    git(code, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "my unpushed work")
    push_to_origin(created_task, tmp_path, TASK.branch, {"new.py": "x\n"})
    before = snapshot(session)

    with pytest.raises(SetupError) as refused:
        session_setup.session_setup(session, home)

    message = str(refused.value)
    assert message.index("code checkout") < message.index("Recreating a sandbox")
    assert TASK.branch in message and "diverged" in message and "my unpushed work" in message
    assert RECREATING in message and "discards" in message
    assert snapshot(session) == before


def test_uncommitted_changes_the_update_would_overwrite_are_refused(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path
) -> None:
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    notes = session.agent_notes_dir
    (notes / TASK.task_file).write_text("# mine\n")
    push_to_origin(created_task, tmp_path, NOTES_BRANCH, {TASK.task_file: "# theirs\n"})
    before = snapshot(session)

    with pytest.raises(SetupError) as refused:
        session_setup.session_setup(session, home)

    message = str(refused.value)
    assert "notes checkout" in message and NOTES_BRANCH in message and TASK.task_file in message
    assert "uncommitted changes" in message and RECREATING in message
    assert snapshot(session) == before
    assert (notes / TASK.task_file).read_text() == "# mine\n"


def test_a_refusal_in_the_notes_leaves_the_code_checkout_where_it_was(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, tmp_path: Path
) -> None:
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    git(session.agent_notes_dir, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "local")
    push_to_origin(created_task, tmp_path, TASK.branch, {"new.py": "x\n"})
    push_to_origin(created_task, tmp_path, NOTES_BRANCH, {"other.md": "x\n"})
    before = snapshot(session)

    with pytest.raises(SetupError, match="notes checkout"):
        session_setup.session_setup(session, home)

    assert snapshot(session) == before
    assert not (session.agent_project_dir / "new.py").exists()


@pytest.mark.parametrize("make", ["detached", "other branch"])
def test_a_notes_worktree_not_on_the_notes_branch_is_refused(
    session_for: SessionFor, built_kit: Path, created_task: Path, home: Path, make: str
) -> None:
    session = session_for(built_kit, created_task)
    session_setup.session_setup(session, home)
    notes = session.agent_notes_dir
    git(notes, "switch", "-q", "--detach") if make == "detached" else git(notes, "switch", "-q", "-c", "elsewhere")
    before = snapshot(session)

    with pytest.raises(SetupError) as refused:
        session_setup.session_setup(session, home)

    message = str(refused.value)
    assert "notes checkout" in message and f"expected {NOTES_BRANCH}" in message
    assert ("detached" if make == "detached" else "elsewhere") in message
    assert RECREATING in message and "discards" in message
    assert snapshot(session) == before
