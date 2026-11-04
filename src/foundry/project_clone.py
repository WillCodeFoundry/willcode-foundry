"""ProjectClone: a project's repository as branches and files; the git details (fetching one commit deep, the
remote's name, refspecs) stay inside it."""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from agent_runtime.git import Git, GitError
from foundry.errors import FoundryError

_REMOTE_NAME = "origin"
# The word the messages use for each type of git tree entry a caller can ask for.
_ENTRY_KIND = {"tree": "dir", "blob": "file"}


class NotOnBranchError(FoundryError):
    """The dir or file asked for isn't on a fetched branch: nothing is at its path, or something of the other kind
    is, such as a dir where a file is wanted."""


class ProjectClone:
    """A shallow clone of the repository at a URL, made with your own access in a folder you give it, holding
    nothing until a branch is checked out. Only the branches needed are fetched, one commit deep. Every commit is
    signed with SSH, using the signing key in your git config.

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

    def fetch_branch(self, branch: str) -> None:
        """Fetch the remote's ``branch``, for fetched_list_dir and fetched_read.

        FoundryError when it has no such branch.
        """
        if branch not in self.branches():
            raise FoundryError(f"the repository has no {branch} branch")
        self._fetch(branch)

    def fetched_list_dir(self, branch: str, path: str) -> list[str]:
        """The names of the dirs directly in ``path`` on ``branch``, as last fetched; files and links are left out.

        Makes no network call. FoundryError when the branch isn't fetched; NotOnBranchError, which nothing else
        raises, when ``path`` isn't a dir there.
        """
        self._require_on_branch(branch, path, "tree")
        return [
            name for entry_type, name in self._ls_tree(f"{self._tracking_ref(branch)}:{path}") if entry_type == "tree"
        ]

    def fetched_read(self, branch: str, path: str) -> str:
        """The text of the file ``path`` on ``branch``, as last fetched; a link reads as its target's name.

        Makes no network call. FoundryError when the branch isn't fetched; NotOnBranchError when ``path`` isn't a
        file there.
        """
        self._require_on_branch(branch, path, "blob")
        return self._git.output("show", f"{self._tracking_ref(branch)}:{path}")

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

    def move_dir(self, src: str, dst: str) -> None:
        """Move the folder ``src``, with everything in it, to ``dst``, both relative to the repository root.

        Creates ``dst``'s parents. Raises FileExistsError if ``dst`` exists. The move is staged, not committed.
        git moves the files it tracks as they are, so your excludes and core.autocrlf can't drop or change one. A
        ``text`` attribute other than ``auto`` in your global gitattributes still can, when commit re-reads a file.
        """
        target = self._work_dir / dst
        if target.exists():
            raise FileExistsError(f"{dst} already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._git.output("mv", src, dst)

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
            *(f"{self._tracking_ref(source)}:refs/heads/{branch}" for branch, source in from_remote.items()),
            *(f"refs/heads/{branch}:refs/heads/{branch}" for branch in from_local),
        ]
        self._git.output("push", "--quiet", "--atomic", _REMOTE_NAME, *refspecs)

    def _require_fetched(self, branch: str) -> None:
        if not self._git.succeeds("rev-parse", "--verify", "--quiet", f"{self._tracking_ref(branch)}^{{commit}}"):
            raise FoundryError(f"{branch} isn't fetched: call fetch_branch first")

    def _require_on_branch(self, branch: str, path: str, entry_type: Literal["tree", "blob"]) -> None:
        """Check ``path`` is an ``entry_type`` entry on ``branch``, as last fetched.

        FoundryError when the branch isn't fetched; NotOnBranchError when nothing is at ``path``, or an entry of
        another type is. Any other git failure is a GitError, never taken for a missing path.
        """
        self._require_fetched(branch)
        entries = self._ls_tree(self._tracking_ref(branch), "--", path)
        if (entry_type, path) not in entries:  # ls-tree lists a dir's contents for "dir/", so match the name exactly
            raise NotOnBranchError(f"{branch} has no {_ENTRY_KIND[entry_type]} {path}")

    def _ls_tree(self, *args: str) -> list[tuple[str, str]]:
        """The type and name of each entry ``git ls-tree`` lists for ``args``."""
        entries = []
        for entry in filter(None, self._git.output("ls-tree", "-z", *args).split("\0")):
            info, _, name = entry.partition("\t")  # "<mode> <type> <object>", a tab, the name
            entries.append((info.split()[1], name))
        return entries

    @staticmethod
    def _tracking_ref(branch: str) -> str:
        """The ref the remote's ``branch`` is fetched into."""
        return f"refs/remotes/{_REMOTE_NAME}/{branch}"

    def _fetch(self, branch: str) -> None:
        """Fetch ``branch``'s latest commit, as refs/remotes/origin/<branch>."""
        self._git.output("fetch", "--quiet", "--depth=1", _REMOTE_NAME, branch)
