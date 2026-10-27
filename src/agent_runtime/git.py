"""Git, the one way the foundry runs git: the runtime in the sandbox, and foundry on the host.

``Git(folder, env)`` runs git in ``folder``, named with git's own ``-C`` (a missing folder is then a failure git
reports, not an exception), or in the current directory, where git runs its hooks. ``env``, when given, is the
whole environment git runs in. The ways to run a command, for what callers need of it:

    output         its output, as text; a failure raises GitError
    output_bytes   its output exactly as git wrote it; a failure raises GitError
    run_captured   the CompletedProcess, captured as text; the caller reads the exit code
    succeeds       whether it exited 0, its output discarded
    run_visibly    whether it exited 0, its output shown to the user as progress

Text is decoded with replacement characters, so output that isn't UTF-8 never raises. A missing git executable
raises GitError from every one. New methods are for what both packages need; host-only conveniences belong in
foundry, built on these.
"""

import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any


class GitError(Exception):
    """A git command failed, or git isn't there to run it; the message says which, in git's own words."""


@dataclass(frozen=True)
class Git:
    """git, acting on one repository, in one environment."""

    folder: Path | None = None
    """The repository git acts on; None for the current directory."""
    env: Mapping[str, str] | None = None
    """The whole environment git runs in; None for this process's."""

    def output(self, *args: str, input: str | None = None) -> str:
        result = self._run(args, input=input, text=True)
        self._raise_on_failure(args, result.returncode, result.stderr)
        stdout: str = result.stdout
        return stdout

    def output_bytes(self, *args: str, input: bytes | None = None) -> bytes:
        result = self._run(args, input=input, text=False)
        self._raise_on_failure(args, result.returncode, result.stderr.decode(errors="replace"))
        stdout: bytes = result.stdout
        return stdout

    def run_captured(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self._run(args, input=None, text=True)

    def succeeds(self, *args: str) -> bool:
        return self._run(args, input=None, text=False, output=subprocess.DEVNULL).returncode == 0

    def run_visibly(self, *args: str, input: bytes | None = None) -> bool:
        """Whether the command exits 0, git writing straight to this process's stdout and stderr, after what this
        process has already written there."""
        sys.stdout.flush()
        sys.stderr.flush()
        return self._run(args, input=input, text=False, output=None).returncode == 0

    def describe(self, *args: str) -> str:
        """The command as a person would type it, ``-C <folder>`` included, quoted with shlex.join."""
        return shlex.join(self._argv(args))

    def current_branch(self) -> str | None:
        """The branch checked out; None when HEAD is detached."""
        result = self.run_captured("symbolic-ref", "--short", "HEAD")
        return result.stdout.strip() if result.returncode == 0 else None

    def _raise_on_failure(self, args: Sequence[str], returncode: int, stderr: str) -> None:
        if returncode != 0:
            raise GitError(f"{self.describe(*args)} failed: {stderr.strip()}")

    def _run(
        self,
        args: Sequence[str],
        *,
        input: str | bytes | None,
        text: bool,
        output: int | IO[Any] | None = subprocess.PIPE,
    ) -> "subprocess.CompletedProcess[Any]":
        try:
            return subprocess.run(
                self._argv(args),
                input=input,
                stdout=output,
                stderr=output,
                text=text,
                errors="replace" if text else None,
                env=dict(self.env) if self.env is not None else None,
                check=False,
            )
        except FileNotFoundError:
            raise GitError("git not found in PATH") from None

    def _argv(self, args: Sequence[str]) -> list[str]:
        folder = ["-C", str(self.folder)] if self.folder is not None else []
        return ["git", *folder, *args]
