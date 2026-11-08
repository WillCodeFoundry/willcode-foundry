"""The GitHub repository behind a project, as a bare repository on disk, and the git config the tests run with:
an identity, a signing key, and a stand-in for ssh-keygen that records which key signed."""

import os
import subprocess
import tempfile
from pathlib import Path

from foundry.project_clone import ProjectClone
from foundry.project_tasks import ProjectTasks
from foundry.task import NOTES_BRANCH, Task

SIGNING_KEY = "ssh-ed25519 AAAATESTKEY"

# Stands in for ssh-keygen as git's SSH signer: git runs it as <program> -Y sign ... -f <key file> ... <payload>,
# and it writes <payload>.sig holding the key it was asked to sign with, so a test can see which key signed.
SIGNER = """#!/bin/sh
while [ $# -gt 1 ]; do case "$1" in -f) key="$2"; shift 2 ;; *) shift ;; esac; done
printf '%s\\n' "-----BEGIN SSH SIGNATURE-----" "$(cat "$key")" "-----END SSH SIGNATURE-----" > "$1.sig"
"""


def write_gitconfig(home_dir: Path) -> None:
    """Your git config: an identity, your signing key, and SIGNER standing in for ssh-keygen."""
    signer = home_dir / "signer"
    signer.write_text(SIGNER)
    signer.chmod(0o755)
    user = f"[user]\n\tname = Owner\n\temail = owner@example.com\n\tsigningkey = key::{SIGNING_KEY}\n"
    (home_dir / ".gitconfig").write_text(f'{user}[gpg "ssh"]\n\tprogram = {signer}\n')


def make_git_env(parent_dir: Path) -> dict[str, str]:
    """The environment git runs in: a throwaway HOME in ``parent_dir`` with write_gitconfig's config, and none of
    the developer's own."""
    home_dir = parent_dir / "home"
    home_dir.mkdir()
    write_gitconfig(home_dir)
    return {"PATH": os.environ["PATH"], "HOME": str(home_dir), "GIT_CONFIG_NOSYSTEM": "1"}


def git_output(env: dict[str, str], *args: str) -> str:
    """git's stripped output, run in ``env``."""
    return subprocess.run(["git", *args], env=env, capture_output=True, text=True, check=True).stdout.strip()


def clone_in(parent_dir: Path, git_env: dict[str, str], url: str) -> ProjectClone:
    """A ProjectClone of ``url`` in a new dir in ``parent_dir``."""
    return ProjectClone.init(url, Path(tempfile.mkdtemp(dir=parent_dir, prefix="scratch-")), git_env)


def project_tasks_of(repository_dir: Path, git_env: dict[str, str]) -> ProjectTasks:
    """The tasks of the repository at ``repository_dir``, as the project store, through a clone of their own."""
    return ProjectTasks(clone_in(repository_dir.parent, git_env, str(repository_dir)))


class ProjectRepository:
    """Stands in for the GitHub repository behind the project store: a bare repository at ``path``.

    Its main has one commit, and its agent-notes holds ``open_task`` and ``closed_task``, each with a TASK.md. Each
    method sees it as it is now. git runs in ``git_env``.
    """

    open_task = Task.as_open("tst-0000")
    closed_task = Task.as_closed("cls-0000")

    def __init__(self, path: Path, git_env: dict[str, str]) -> None:
        self.path = path
        self.git_env = git_env

    def git(self, *args: str) -> str:
        """git's stripped output, run on the bare repository."""
        return git_output(self.git_env, f"--git-dir={self.path}", *args)

    def clone(self, env: dict[str, str] | None = None) -> ProjectClone:
        """A ProjectClone of it in a new dir, with git run in ``env``, or ``git_env``."""
        return clone_in(self.path.parent, env or self.git_env, str(self.path))

    def fetched_clone(self) -> ProjectClone:
        """A ProjectClone of it, with agent-notes fetched."""
        clone = self.clone()
        clone.fetch_branch(NOTES_BRANCH)
        return clone

    def project_tasks(self, env: dict[str, str] | None = None) -> ProjectTasks:
        """Its tasks, through a clone of their own, with git run in ``env``, or ``git_env``."""
        return project_tasks_of(self.path, env or self.git_env)

    def edit_notes(self, *, write=None, symlink=None, remove=()) -> None:
        """Commit to agent-notes and push it, as an agent would: files to ``write``, links to ``symlink`` (path ->
        target), paths to ``remove``."""
        work_dir = Path(tempfile.mkdtemp(dir=self.path.parent, prefix="edit-"))
        git_output(self.git_env, "clone", "--quiet", "--branch", NOTES_BRANCH, str(self.path), str(work_dir))
        for path, text in (write or {}).items():
            (work_dir / path).parent.mkdir(parents=True, exist_ok=True)
            (work_dir / path).write_text(text)
        for path, target in (symlink or {}).items():
            (work_dir / path).parent.mkdir(parents=True, exist_ok=True)
            (work_dir / path).symlink_to(target)
        for path in remove:
            git_output(self.git_env, "-C", str(work_dir), "rm", "-rq", path)
        git_output(self.git_env, "-C", str(work_dir), "add", "-A")
        git_output(self.git_env, "-C", str(work_dir), "commit", "--quiet", "-m", "edit")
        git_output(self.git_env, "-C", str(work_dir), "push", "--quiet", "origin", NOTES_BRANCH)

    def notes_files(self) -> dict[str, str]:
        """Each file on agent-notes, by path: its text, stripped, then a newline."""
        paths = self.git("ls-tree", "-r", "--name-only", NOTES_BRANCH).splitlines()
        return {path: self.git("show", f"{NOTES_BRANCH}:{path}") + "\n" for path in paths}

    def notes_tree(self) -> dict[str, str]:
        """Each file on agent-notes, by path: its mode and blob."""
        listing = self.git("ls-tree", "-r", NOTES_BRANCH).splitlines()
        return {
            path: mode_type_blob.replace(" blob ", " ")
            for mode_type_blob, path in (line.split("\t") for line in listing)
        }

    def notes_commits(self) -> list[str]:
        """The subject of each commit on agent-notes, newest first."""
        return self.git("log", "--format=%s", NOTES_BRANCH).splitlines()

    def head(self, branch: str) -> str:
        """The commit at ``branch``'s tip."""
        return self.git("rev-parse", f"refs/heads/{branch}")

    def notes_head(self) -> str:
        """The commit at agent-notes' tip."""
        return self.head(NOTES_BRANCH)

    def notes_signed_with_your_key(self) -> bool:
        """Whether agent-notes' last commit is signed with SIGNING_KEY."""
        commit = self.git("cat-file", "commit", NOTES_BRANCH)
        return f"gpgsig -----BEGIN SSH SIGNATURE-----\n {SIGNING_KEY}\n" in commit

    @classmethod
    def seed(cls, parent_dir: Path, git_env: dict[str, str]) -> "ProjectRepository":
        """A new one in ``parent_dir``, with its main commit and agent-notes' two tasks pushed."""
        path, seed_dir = parent_dir / "origin.git", parent_dir / "seed"
        git_output(git_env, "init", "--quiet", "--bare", "--initial-branch=main", str(path))
        git_output(git_env, "init", "--quiet", "--initial-branch=main", str(seed_dir))
        (seed_dir / "README.md").write_text("code\n")
        git_output(git_env, "-C", str(seed_dir), "add", ".")
        git_output(git_env, "-C", str(seed_dir), "commit", "--quiet", "-m", "init")
        git_output(git_env, "-C", str(seed_dir), "switch", "--quiet", "--orphan", NOTES_BRANCH)
        for seeded in (cls.open_task, cls.closed_task):
            (seed_dir / seeded.task_notes_dir).mkdir(parents=True)
            (seed_dir / seeded.task_file).write_text(f"{seeded.id}\n")
        git_output(git_env, "-C", str(seed_dir), "add", ".agent")
        git_output(git_env, "-C", str(seed_dir), "commit", "--quiet", "-m", "T0")
        git_output(git_env, "-C", str(seed_dir), "push", "--quiet", str(path), "main", NOTES_BRANCH)
        return cls(path, git_env)
