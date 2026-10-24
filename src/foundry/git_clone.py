"""A shallow clone of a project's repository in a scratch directory, made and pushed with git as the person running
foundry: only the branches needed are fetched, one commit deep."""

import subprocess
from collections.abc import Mapping
from pathlib import Path

from foundry.errors import FoundryError

REMOTE_NAME = "origin"


class GitClone:
    """A clone of the repository at a URL, in ``work_dir``, holding nothing until branches are fetched.

    ``env`` is the environment git runs in: it carries the person's git config (identity, signing) and SSH agent.
    """

    def __init__(self, work_dir: Path, env: Mapping[str, str]) -> None:
        self.work_dir = work_dir
        self._env = dict(env)

    @classmethod
    def init(cls, url: str, work_dir: Path, env: Mapping[str, str]) -> "GitClone":
        """Create an empty repository in ``work_dir``, an existing empty directory, with ``url`` as its remote."""
        clone = cls(work_dir, env)
        clone._git("init", "--quiet")
        clone._git("remote", "add", REMOTE_NAME, url)
        return clone

    def default_branch(self) -> str | None:
        """The remote's default branch, or None for a repository with no commits yet."""
        for line in self._git("ls-remote", "--symref", REMOTE_NAME, "HEAD").splitlines():
            if line.startswith("ref: "):
                return line.removeprefix("ref: refs/heads/").partition("\t")[0]
        return None

    def branches(self) -> list[str]:
        """The names of the remote's branches."""
        return [
            line.partition("\t")[2].removeprefix("refs/heads/")
            for line in self._git("ls-remote", "--heads", REMOTE_NAME).splitlines()
        ]

    def fetch(self, branch: str) -> None:
        """Fetch ``branch``'s latest commit, as origin/<branch>."""
        self._git("fetch", "--quiet", "--depth=1", REMOTE_NAME, branch)

    def switch(self, branch: str) -> None:
        """Check out a fetched branch."""
        self._git("switch", "--quiet", branch)

    def switch_orphan(self, branch: str) -> None:
        """Start ``branch`` with no history and no files."""
        self._git("switch", "--quiet", "--orphan", branch)

    def commit(self, path: str, message: str) -> None:
        """Commit everything under ``path`` (relative to ``work_dir``)."""
        self._git("add", "--", path)
        self._git("commit", "--quiet", "--message", message)

    def push_atomic(self, branch_sources: Mapping[str, str]) -> None:
        """Push each local revision to its remote branch, all or none: branch name -> revision, e.g. origin/main."""
        refspecs = [f"{revision}:refs/heads/{branch}" for branch, revision in branch_sources.items()]
        self._git("push", "--quiet", "--atomic", REMOTE_NAME, *refspecs)

    def _git(self, *args: str) -> str:
        """Run git in ``work_dir`` and return its output; raise with git's message if it fails."""
        try:
            result = subprocess.run(
                ["git", "-C", str(self.work_dir), *args], check=False, capture_output=True, text=True, env=self._env
            )
        except FileNotFoundError:
            raise FoundryError("git not found in PATH") from None
        if result.returncode != 0:
            raise FoundryError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result.stdout
