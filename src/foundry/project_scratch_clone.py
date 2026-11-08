"""A scratch clone of a project repository, and the branches fetched into it. The git details (fetching one commit
deep, the remote's name, refspecs) stay in this module.

| Class | Does |
|---|---|
| ProjectScratchClone | fetches, checks out, writes, commits and pushes: all that changes the clone or the remote |
| FetchedBranch | reads one fetched branch at its commit, without a checkout: it can change nothing |
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from agent_runtime.git import Git, GitError
from foundry.errors import FoundryError

_REMOTE_NAME = "origin"
# The word the messages use for each type of git tree entry a caller can ask for.
_ENTRY_WORD_BY_TYPE = {"tree": "dir", "blob": "file"}


class BranchNotFoundError(FoundryError):
    """The remote has no branch of that name."""


class PathNotOnBranchError(FoundryError):
    """The dir or file asked for isn't on a fetched branch. Either nothing is at its path, or something of the
    other kind is, such as a dir where a file is wanted."""


class FetchedBranch:
    """A branch of the project repository as one fetch found it: its name, and the commit it pointed at. Made by
    ProjectScratchClone.fetch_branch. Its files are read at that commit, whatever the remote has since, and no read
    makes a network call. ProjectScratchClone.check_out checks it out at that commit too."""

    def __init__(self, git: Git, name: str, commit: str) -> None:
        self._git = git
        self.name = name
        self.commit = commit

    def subdir_names(self, path: str) -> list[str]:
        """The names of the dirs directly in ``path``; files and links are left out.

        PathNotOnBranchError, which nothing else raises, when ``path`` isn't a dir here.
        """
        self._require_entry(path, "tree")
        return [name for entry_type, name in _ls_tree(self._git, f"{self.commit}:{path}") if entry_type == "tree"]

    def read_text(self, path: str) -> str:
        """The text of the file ``path``; a link reads as its target's name.

        PathNotOnBranchError when ``path`` isn't a file here.
        """
        self._require_entry(path, "blob")
        return self._git.output("show", f"{self.commit}:{path}")

    def _require_entry(self, path: str, entry_type: Literal["tree", "blob"]) -> None:
        """Check ``path`` is an ``entry_type`` entry.

        PathNotOnBranchError when nothing is at ``path``, or an entry of another type is. Any other git failure is a
        GitError, never taken for a missing path.
        """
        entries = _ls_tree(self._git, self.commit, "--", path)
        if (entry_type, path) not in entries:  # ls-tree lists a dir's contents for "dir/", so match the name exactly
            raise PathNotOnBranchError(f"{self.name} has no {_ENTRY_WORD_BY_TYPE[entry_type]} {path}")


class ProjectScratchClone:
    """A scratch clone: a shallow clone of the project repository at a URL, made with your own access in a dir you
    give it. It holds nothing until a branch is fetched; the FetchedBranch it returns is read without a checkout.
    Only the branches needed are fetched, one commit deep. Every commit is signed with SSH, using the signing key
    in your git config.

    ``env`` is the environment git runs in: it carries your git config (identity, signing key) and SSH agent.
    A git failure is a GitError; a failed commit's adds how to sign.
    """

    def __init__(self, work_dir: Path, env: Mapping[str, str]) -> None:
        self._work_dir = work_dir
        self._git = Git(work_dir, dict(env))

    @classmethod
    def init(cls, url: str, work_dir: Path, env: Mapping[str, str]) -> "ProjectScratchClone":
        """Make ``work_dir``, an existing empty dir, into an empty clone with the remote at ``url``.

        It signs every commit, with SSH (not GPG, which allowed_signers can't verify) and your user.signingkey.
        """
        clone = cls(work_dir, env)
        clone._git.output("init", "--quiet")
        clone._git.output("remote", "add", _REMOTE_NAME, url)
        clone._git.output("config", "gpg.format", "ssh")
        clone._git.output("config", "commit.gpgsign", "true")
        return clone

    def default_branch(self) -> str | None:
        """The remote's default branch, or None when it has no commits yet."""
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

    def fetch_branch(self, branch: str) -> FetchedBranch:
        """Fetch the remote's ``branch``, one commit deep, and return it as fetched.

        BranchNotFoundError when the remote has no such branch.
        """
        if branch not in self.branches():
            raise BranchNotFoundError(f"the project repository has no {branch} branch")
        self._fetch(branch)
        commit = self._git.output("rev-parse", f"{self._tracking_ref(branch)}^{{commit}}").strip()
        return FetchedBranch(self._git, branch, commit)

    def check_out(self, fetched: FetchedBranch) -> None:
        """Check ``fetched`` out at its commit, so what is written next lands on what was read. Makes no network
        call."""
        self._git.output("switch", "--quiet", "--force-create", fetched.name, fetched.commit)

    def start_orphan(self, branch: str) -> None:
        """Check out a new ``branch`` with no history and no files, for one the remote doesn't have yet."""
        self._git.output("switch", "--quiet", "--orphan", branch)

    def write(self, files: Mapping[str, str]) -> None:
        """Write each file, by path relative to the working tree's root, creating dirs and replacing files as needed.

        FoundryError when a path is a link, which could point outside the clone. Nothing is staged or committed.
        """
        for path, text in files.items():
            file_path = self._work_dir / path
            if file_path.is_symlink():
                raise FoundryError(f"{path} is a link: foundry writes only files")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(text)

    def move_dir(self, src: str, dst: str) -> None:
        """Move the dir ``src``, with everything in it, to ``dst``, both relative to the working tree's root.

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
        if not (from_remote or from_local):
            raise ValueError("push_atomic needs at least one branch to push")  # a programming error
        for source in dict.fromkeys(from_remote.values()):
            self._fetch(source)
        refspecs = [
            *(f"{self._tracking_ref(source)}:refs/heads/{branch}" for branch, source in from_remote.items()),
            *(f"refs/heads/{branch}:refs/heads/{branch}" for branch in from_local),
        ]
        self._git.output("push", "--quiet", "--atomic", _REMOTE_NAME, *refspecs)

    @staticmethod
    def _tracking_ref(branch: str) -> str:
        """The ref the remote's ``branch`` is fetched into."""
        return f"refs/remotes/{_REMOTE_NAME}/{branch}"

    def _fetch(self, branch: str) -> None:
        """Fetch ``branch``'s latest commit, as refs/remotes/origin/<branch>."""
        self._git.output("fetch", "--quiet", "--depth=1", _REMOTE_NAME, branch)


def _ls_tree(git: Git, *args: str) -> list[tuple[str, str]]:
    """The type and name of each entry ``git ls-tree`` lists for ``args``."""
    entries = []
    for entry in filter(None, git.output("ls-tree", "-z", *args).split("\0")):
        header, _, name = entry.partition("\t")  # "<mode> <type> <object>", a tab, the name
        entries.append((header.split()[1], name))
    return entries
