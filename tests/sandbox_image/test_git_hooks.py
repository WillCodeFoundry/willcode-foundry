"""agent-kit/hooks/ as written, by real commits and pushes as the agent, in a container hardened by a first launch:
the stubs run the runtime through the link root mode made, on the template's /usr/bin/python3, from the
read-only mount. A host has no such link, so this is where the stubs run; their rules are tested in-process in
tests/agent_runtime/test_git_hooks.py, and the git-hook command in tests/agent_kit/test_git_hook_command.py.
"""

import shlex
import subprocess

import pytest

from foundry.task import NOTES_BRANCH, Task
from tests.support import TASK, UNSIGNED
from tests.support.docker import AGENT_HOME, Sandbox

pytestmark = pytest.mark.docker

RUNTIME_LINK = "/etc/claude-code/agent_runtime.pyz"


class Checkouts:
    """The task's two checkouts in a container hardened by a first launch, worked in as the agent."""

    def __init__(self, sandbox: Sandbox) -> None:
        self.container, self.env = sandbox()
        launched = self.container.session_init(self.env)
        assert launched.returncode == 0, launched.stdout + launched.stderr
        self.code, self.notes = self.env["AGENT_PROJECT_DIR"], self.env["AGENT_NOTES_DIR"]

    def git(self, cwd: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """git as the agent, with the session's variables; signing is off, as the roles' keys aren't here."""
        return self.container.run("agent", "git", "-C", cwd, *args, env={**self.env, **UNSIGNED, **(env or {})})

    def change(self, cwd: str, name: str) -> None:
        path = shlex.quote(f"{cwd}/{name}")
        written = self.container.shell("agent", f"mkdir -p $(dirname {path}) && echo {path} > {path}")
        assert written.returncode == 0, written.stderr
        assert self.git(cwd, "add", name).returncode == 0

    def commits(self, cwd: str) -> int:
        return int(self.git(cwd, "rev-list", "--count", "HEAD").stdout)


@pytest.fixture
def checkouts(sandbox: Sandbox) -> Checkouts:
    return Checkouts(sandbox)


def test_a_commit_on_the_task_branch_gets_the_task_trailer_even_with_no_verify(checkouts: Checkouts) -> None:
    for name, *no_verify in [("hello.sh",), ("bye.sh", "--no-verify")]:
        checkouts.change(checkouts.code, name)

        committed = checkouts.git(checkouts.code, "commit", "-q", *no_verify, "-m", f"feat: {name}")

        assert committed.returncode == 0, committed.stderr
        message = checkouts.git(checkouts.code, "log", "-1", "--format=%B").stdout
        assert message.rstrip("\n").endswith(f"\n\nTask: {TASK.id}"), message


def test_notes_on_the_task_branch_are_refused(checkouts: Checkouts) -> None:
    checkouts.change(checkouts.code, f"{TASK.notes_dir}/PROGRESS.md")
    before = checkouts.commits(checkouts.code)

    refused = checkouts.git(checkouts.code, "commit", "-q", "-m", "notes")

    assert refused.returncode != 0
    assert "pre-commit: refusing" in refused.stderr and f"Task notes belong on {NOTES_BRANCH}" in refused.stderr
    assert checkouts.commits(checkouts.code) == before


def test_only_the_tasks_own_branch_and_the_notes_branch_can_be_pushed(checkouts: Checkouts) -> None:
    checkouts.change(checkouts.code, "hello.sh")
    assert checkouts.git(checkouts.code, "commit", "-q", "-m", "feat: hello").returncode == 0
    checkouts.change(checkouts.notes, f"{TASK.notes_dir}/PROGRESS.md")
    assert checkouts.git(checkouts.notes, "commit", "-q", "-m", f"{TASK.id}: progress").returncode == 0

    assert checkouts.git(checkouts.code, "push", "-q", "origin", TASK.branch).returncode == 0
    assert checkouts.git(checkouts.notes, "push", "-q", "origin", NOTES_BRANCH).returncode == 0
    for target in ("HEAD:refs/heads/other", f"HEAD:refs/heads/{Task('T2').branch}", "HEAD:refs/tags/v1"):
        refused = checkouts.git(checkouts.code, "push", "origin", target)
        assert refused.returncode != 0 and "pre-push: refusing" in refused.stderr, target


def test_what_the_agent_sets_in_its_environment_changes_no_rule(checkouts: Checkouts) -> None:
    """The agent sets its git commands' environment. Each of these would approve the commit if the stubs read
    it: a startup file for the shell, a sitecustomize and a pathlib ahead of the standard library's, a kit
    elsewhere. (Not PYTHONHOME: a wrong one stops Python starting, which refuses the commit whatever the flags.)"""
    agents_own = f"{AGENT_HOME}/agents-own"
    approve = "raise SystemExit(0)"
    planted = checkouts.container.shell(
        "agent",
        f"mkdir -p {agents_own} && echo 'exit 0' > {agents_own}/startup.sh"
        f" && for module in sitecustomize pathlib; do echo '{approve}' > {agents_own}/$module.py; done",
    )
    assert planted.returncode == 0, planted.stderr
    checkouts.change(checkouts.code, f"{TASK.notes_dir}/PROGRESS.md")

    refused = checkouts.git(
        checkouts.code,
        "commit", "-q", "-m", "notes",
        env={
            "ENV": f"{agents_own}/startup.sh",
            "BASH_ENV": f"{agents_own}/startup.sh",
            "PYTHONPATH": agents_own,
            "AGENT_KIT_DIR": f"{agents_own}/kit",
        },
    )  # fmt: skip

    assert refused.returncode != 0
    assert f"Task notes belong on {NOTES_BRANCH}" in refused.stderr


def test_without_the_runtimes_link_git_stops(checkouts: Checkouts) -> None:
    """Rather than commit with no rules run: a sandbox hardened by a kit older than the link, say."""
    removed = checkouts.container.run("root", "rm", RUNTIME_LINK)
    assert removed.returncode == 0, removed.stderr
    checkouts.change(checkouts.code, "hello.sh")
    before = checkouts.commits(checkouts.code)

    refused = checkouts.git(checkouts.code, "commit", "-q", "-m", "feat: hello")

    assert refused.returncode != 0
    assert RUNTIME_LINK in refused.stderr
    assert checkouts.commits(checkouts.code) == before
