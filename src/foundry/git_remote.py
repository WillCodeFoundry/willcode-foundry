"""A project's repository reached with git itself, as the person running foundry.

Commits are made without a checkout, in a bare scratch repository: only the
branches needed are fetched, shallow, and the files are written with git's
plumbing commands.
"""

import subprocess
from collections.abc import Mapping
from pathlib import Path

from foundry.errors import FoundryError

REMOTE_NAME = "origin"


class GitRemote:
    """The repository at a URL, through the bare scratch repository at ``scratch_dir``.

    ``env`` is the environment git runs in: it carries the person's git config (identity, signing) and SSH agent.
    """

    def __init__(self, scratch_dir: Path, env: Mapping[str, str]) -> None:
        self._scratch_dir = scratch_dir
        self._env = dict(env)

    @classmethod
    def init(cls, url: str, scratch_dir: Path, env: Mapping[str, str]) -> "GitRemote":
        """Create the scratch repository in ``scratch_dir`` with ``url`` as its remote."""
        remote = cls(scratch_dir, env)
        remote._git("init", "--quiet", "--bare")
        remote._git("remote", "add", REMOTE_NAME, url)
        return remote

    def default_branch(self) -> str | None:
        """The branch the remote's HEAD names, or None for a repository with no commits yet."""
        for line in self._git("ls-remote", "--symref", REMOTE_NAME, "HEAD").splitlines():
            if line.startswith("ref: "):
                return line.removeprefix("ref: refs/heads/").partition("\t")[0]
        return None

    def branch_heads(self) -> dict[str, str]:
        """The commit sha of each of the remote's branches, by name."""
        heads = {}
        for line in self._git("ls-remote", "--heads", REMOTE_NAME).splitlines():
            sha, _, ref = line.partition("\t")
            heads[ref.removeprefix("refs/heads/")] = sha
        return heads

    def fetch_commit(self, branch: str) -> str:
        """Fetch the commit ``branch`` points at, without its files, and return its sha."""
        return self._fetch(branch, "--filter=tree:0")

    def fetch_tree(self, branch: str) -> str:
        """Fetch the commit ``branch`` points at, with its files, and return its sha."""
        return self._fetch(branch)

    def paths(self, commit_sha: str, directory: str) -> list[str]:
        """The files under ``directory`` in a fetched commit."""
        return self._git("ls-tree", "-r", "--name-only", commit_sha, "--", f"{directory}/").splitlines()

    def commit_files(self, files: Mapping[str, str], commit_message: str, *, parent_sha: str | None) -> str:
        """A commit writing ``files`` (path -> text) on top of the fetched ``parent_sha``, or a parentless one
        holding only them; return its sha. Nothing is pushed."""
        index_env = {"GIT_INDEX_FILE": str(self._scratch_dir / "foundry-index")}
        if parent_sha is None:
            self._git("read-tree", "--empty", extra_env=index_env)
        else:
            self._git("read-tree", parent_sha, extra_env=index_env)
        for path, text in files.items():
            blob_sha = self._git("hash-object", "-w", "--stdin", stdin=text).strip()
            self._git("update-index", "--add", "--cacheinfo", f"100644,{blob_sha},{path}", extra_env=index_env)
        tree_sha = self._git("write-tree", extra_env=index_env).strip()
        parent_args = [] if parent_sha is None else ["-p", parent_sha]
        return self._git("commit-tree", tree_sha, *parent_args, "-m", commit_message).strip()

    def push_atomic(self, branch_shas: Mapping[str, str]) -> None:
        """Point each branch at its sha on the remote, all or none. A branch that moved meanwhile is refused."""
        refspecs = [f"{sha}:refs/heads/{branch}" for branch, sha in branch_shas.items()]
        self._git("push", "--quiet", "--atomic", REMOTE_NAME, *refspecs)

    def _fetch(self, branch: str, *options: str) -> str:
        self._git("fetch", "--quiet", "--depth=1", *options, REMOTE_NAME, f"refs/heads/{branch}")
        return self._git("rev-parse", "FETCH_HEAD").strip()

    def _git(self, *args: str, stdin: str | None = None, extra_env: Mapping[str, str] | None = None) -> str:
        """Run git on the scratch repository and return its output; raise with git's message if it fails."""
        command = ["git", f"--git-dir={self._scratch_dir}", *args]
        try:
            result = subprocess.run(
                command,
                check=False,
                input=stdin,
                capture_output=True,
                text=True,
                env={**self._env, **(extra_env or {})},
            )
        except FileNotFoundError:
            raise FoundryError("git not found in PATH") from None
        if result.returncode != 0:
            raise FoundryError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result.stdout
