"""ProjectClone: a shallow clone of a project's repository, in a folder you give it, made and pushed with git and
your own access. It speaks in branches and files; the git details (fetching one commit deep, the remote's
name, refspecs) stay inside it."""

from collections.abc import Mapping
from pathlib import Path

from agent_runtime.git import Git, GitError

_REMOTE_NAME = "origin"


class ProjectClone:
    """A clone of the repository at a URL, in a folder you give it, holding nothing until a branch is checked out.

    Lists the remote's branches, checks one out (starting it empty if the remote doesn't have it), checks and
    writes files in it, commits them, and pushes branches together. Only the branches needed are fetched, one
    commit deep. Every commit is signed with SSH, using the signing key in your git config.

    ``env`` is the environment git runs in: it carries your git config (identity, signing key) and SSH agent.
    A git failure is a GitError; a failed commit's adds how to sign.
    """

    def __init__(self, work_dir: Path, env: Mapping[str, str]) -> None:
        self._work_dir = work_dir
        self._git = Git(work_dir, dict(env))

    @classmethod
    def init(cls, url: str, work_dir: Path, env: Mapping[str, str]) -> "ProjectClone":
        """Create an empty repository in ``work_dir``, an existing empty folder, with ``url`` as its remote.

        It signs every commit, with SSH (not GPG, which allowed_signers can't verify) and your user.signingkey.
        """
        clone = cls(work_dir, env)
        clone._git.output("init", "--quiet")
        clone._git.output("remote", "add", _REMOTE_NAME, url)
        clone._git.output("config", "gpg.format", "ssh")
        clone._git.output("config", "commit.gpgsign", "true")
        return clone

    def default_branch(self) -> str | None:
        """The remote's default branch, or None for a repository with no commits yet."""
        for line in self._git.output("ls-remote", "--symref", _REMOTE_NAME, "HEAD").splitlines():
            if line.startswith("ref: "):
                return line.removeprefix("ref: refs/heads/").partition("\t")[0]
        return None

    def branches(self) -> list[str]:
        """The names of the remote's branches."""
        return [
            line.partition("\t")[2].removeprefix("refs/heads/")
            for line in self._git.output("ls-remote", "--heads", _REMOTE_NAME).splitlines()
        ]

    def check_out(self, branch: str) -> None:
        """Check out ``branch``: its latest commit if the remote has it, otherwise a start with no history or files."""
        if branch in self.branches():  # listed here on purpose, so callers needn't say whether it exists
            self._fetch(branch)
            self._git.output("switch", "--quiet", branch)
        else:
            self._git.output("switch", "--quiet", "--orphan", branch)

    def exists(self, path: str) -> bool:
        """Whether ``path``, relative to the repository root, exists in the checked-out files."""
        return (self._work_dir / path).exists()

    def write(self, files: Mapping[str, str]) -> None:
        """Write each file, by path relative to the repository root, creating folders and replacing files as needed.

        Nothing is staged or committed.
        """
        for path, text in files.items():
            file_path = self._work_dir / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(text)

    def commit(self, message: str) -> None:
        """Commit everything changed in the checked-out files, signed with your signing key."""
        self._git.output("add", "--all")
        try:
            self._git.output("commit", "--quiet", "--message", message)
        except GitError as error:
            raise GitError(
                f"{error}\n"
                "  commits are signed with SSH: set user.signingkey in your global git config to your "
                "public key, as in agent-kit/git/allowed_signers, and check your ssh-agent holds it (ssh-add -L)"
            ) from None

    def push_atomic(self, *, from_remote: Mapping[str, str], from_local: list[str]) -> None:
        """Push branches together, all or none, never forced.

        ``from_remote`` points each new branch on the remote at one of the remote's existing branches:
        {"task/t1": "main"}. ``from_local`` pushes each local branch to the same name on the remote.
        """
        assert from_remote or from_local, "push_atomic needs at least one branch to push"  # a programming error
        for source in dict.fromkeys(from_remote.values()):
            self._fetch(source)
        refspecs = [
            *(f"refs/remotes/{_REMOTE_NAME}/{source}:refs/heads/{branch}" for branch, source in from_remote.items()),
            *(f"refs/heads/{branch}:refs/heads/{branch}" for branch in from_local),
        ]
        self._git.output("push", "--quiet", "--atomic", _REMOTE_NAME, *refspecs)

    def _fetch(self, branch: str) -> None:
        """Fetch ``branch``'s latest commit, as refs/remotes/origin/<branch>."""
        self._git.output("fetch", "--quiet", "--depth=1", _REMOTE_NAME, branch)
