import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest
from _pytest.mark.expression import Expression

from agent_runtime import contract
from foundry import session
from foundry.config import Project, Role
from foundry.runtime_build import build_runtime
from foundry.task import NOTES_BRANCH, Task
from tests.support import AGENT_KIT_SOURCE, SANDBOX_IMAGE, TASK, git, isolate_from_the_developer
from tests.support.project_repository import ProjectRepository, make_git_env


def pytest_configure(config: pytest.Config) -> None:
    """Before anything is collected: stop a run started as root, then set up the environment every test runs in.

    Only the docker tier's containers use root, inside them. The environment is set once, for the whole run,
    rather than patched per test:

    - git acts on the repositories the tests name, never one the run inherited, as when it runs from a git hook.
    - A run of the host tier alone runs as on a fresh machine, as isolate_from_the_developer says. The docker and
      sbx tiers need the real machine, so a run that can select them keeps its environment."""
    if os.geteuid() == 0:
        raise pytest.UsageError(
            "the tests run as an ordinary user, never as root: "
            "root can write anything, so the write checks would mean nothing"
        )
    for name in GIT_REPOSITORY_VARIABLES:
        os.environ.pop(name, None)
    markexpr = config.option.markexpr or ""
    if not any(_selects(markexpr, tier) for tier in ("docker", "sbx")):
        home = Path(tempfile.mkdtemp(prefix="pytest-home-"))
        config.stash[_ISOLATED_HOME] = home
        isolate_from_the_developer(os.environ, home)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove the throwaway HOME the run was given, if it was given one."""
    if _ISOLATED_HOME in config.stash:
        shutil.rmtree(config.stash[_ISOLATED_HOME], ignore_errors=True)


_ISOLATED_HOME = pytest.StashKey[Path]()


def _selects(markexpr: str, marker: str) -> bool:
    """Whether the marker expression selects a test marked only ``marker``. No expression selects every test."""
    return not markexpr or Expression.compile(markexpr).evaluate(_MarkedOnly(marker))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Leave out the sbx tier unless -m asks for it: it launches a real sandbox and removes it with
    `sbx env rm --force` in this foundry, so a -m replacing the default deselection mustn't bring it back."""
    if _asks_for_sbx(config.option.markexpr or ""):
        return
    sbx = [item for item in items if item.get_closest_marker("sbx")]
    if sbx:
        items[:] = [item for item in items if not item.get_closest_marker("sbx")]
        config.hook.pytest_deselected(items=sbx)


def _asks_for_sbx(markexpr: str) -> bool:
    """Whether the marker expression selects a test only when it is marked sbx: true for an sbx test with no
    other marker, false for a test with none."""
    if not markexpr:
        return False
    expression = Expression.compile(markexpr)
    return expression.evaluate(_MarkedOnly("sbx")) and not expression.evaluate(_MarkedOnly())


class _MarkedOnly:
    """A test with these markers and no other, as a marker expression sees it."""

    def __init__(self, *markers: str) -> None:
        self._markers = markers

    def __call__(self, name: str, /, **kwargs: str | int | bool | None) -> bool:
        return name in self._markers


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, config: pytest.Config) -> None:
    """Name the image a -m docker run tested, pass or fail: the tests follow its tag, so the digest is what
    tells two runs' images apart."""
    if (image := config.stash.get(SANDBOX_IMAGE, None)) is not None:
        terminalreporter.write_line(f"sandbox image: {image}")


@pytest.fixture
def session_variables(tmp_path: Path) -> Callable[[Task], contract.SessionVariables]:
    """The session variables a new sandbox for a task gets, from a real session under tmp_path/foundry.

    For a stand-in project and role: tests that need the variables, not a particular project.
    """

    def variables(task: Task) -> contract.SessionVariables:
        opened = session.open_or_create(
            tmp_path / "foundry",
            project=Project(name="p", url="git@github.com:o/p.git"),
            role=Role(name="dev", ssh_key_path=tmp_path / "secrets" / "ssh" / "dev", github_token_path=None),
            task=task,
        )
        return contract.read_session_variables(opened.definition.variables)

    return variables


@pytest.fixture(scope="session")
def built_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of this repository's agent kit with the runtime built into it, made once per test run.

    Tests that run the kit as delivered use it, so none of them writes into the repository's agent-kit/.build/.
    Read-only by agreement: a test that changes the kit makes its own copy.
    """
    kit = tmp_path_factory.mktemp("built") / "agent-kit"
    shutil.copytree(AGENT_KIT_SOURCE, kit, symlinks=True, ignore=shutil.ignore_patterns(".build"))
    build_runtime(kit)
    return kit


# --- a project's origin, for setting a sandbox up against ----------------------------------

GIT_REPOSITORY_VARIABLES = tuple(
    subprocess.run(["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True, check=True).stdout.split()
)
"""The variables that point git at a repository or add configuration, as git lists them: GIT_DIR,
GIT_INDEX_FILE, GIT_CONFIG_PARAMETERS, GIT_CONFIG_COUNT and the rest. A git hook exports some of them."""


@pytest.fixture
def git_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway HOME under tmp_path, with a global git identity and signing off: the developer's own git
    configuration, global or system, stays out. Returns the HOME.

    git finds global configuration through XDG_CONFIG_HOME and GIT_CONFIG_GLOBAL as well as HOME, so both are
    pointed into the throwaway HOME, or `git config --global` would write to the developer's own file."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key, value in {"user.name": "t", "user.email": "t@t", "commit.gpgsign": "false"}.items():
        git(tmp_path, "config", "--global", key, value)
    return home


@pytest.fixture
def origin(tmp_path: Path, git_identity: Path) -> Path:
    """A repository with only main: no task branch, no agent-notes."""
    bare = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-q", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(bare), str(seed))
    (seed / "README.md").write_text("hi\n")
    git(seed, "add", ".")
    git(seed, "commit", "-qm", "init")
    git(seed, "push", "-q", "origin", "HEAD:main")
    return bare


@pytest.fixture
def created_task(tmp_path: Path, origin: Path) -> Path:
    """The origin once `foundry task create` has run: the task's branch, and its TASK.md on the notes branch."""
    seed = tmp_path / "seed"
    git(seed, "push", "-q", "origin", f"HEAD:refs/heads/{TASK.branch}")
    git(seed, "switch", "-q", "--orphan", NOTES_BRANCH)
    (seed / TASK.task_notes_dir).mkdir(parents=True)
    (seed / TASK.task_file).write_text("# Task\n")
    git(seed, "add", TASK.task_notes_dir)
    git(seed, "commit", "-qm", f"Add task {TASK.id}")
    git(seed, "push", "-q", "origin", NOTES_BRANCH)
    return origin


@pytest.fixture
def git_env(tmp_path: Path) -> dict[str, str]:
    """git with a throwaway identity and your signing key, and none of the developer's own config."""
    return make_git_env(tmp_path)


@pytest.fixture
def project_repository(tmp_path: Path, git_env) -> ProjectRepository:
    """The GitHub repository behind the project store, seeded: see ProjectRepository."""
    return ProjectRepository.seed(tmp_path, git_env)
