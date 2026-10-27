"""Git, the one way the foundry runs git: the runtime in the sandbox, and foundry on the host.

``Git(folder, env)`` runs git in ``folder``, named with git's own ``-C`` (unlike a subprocess working directory,
a missing one is a failure git reports, not an exception), or in the current directory, where git runs its
hooks. ``env``, when given, is the whole environment git runs in. Four ways to run a command, for what callers
need of it:

    output         its output, as text; a failure raises GitError
    output_bytes   its output exactly as git wrote it; a failure raises GitError
    result         the CompletedProcess, captured as text; the caller reads the exit code
    succeeds       whether it exited 0; git's own output is discarded, or shown, as progress

A missing git executable raises GitError from every one.
"""

import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


class GitError(Exception):
    """A git command failed, or git isn't there to run it."""

    def __init__(self, command: Sequence[str], stderr: str, *, found: bool = True) -> None:
        self.command = tuple(command)
        """The arguments as the caller passed them, without the -C Git adds."""
        self.stderr = stderr
        super().__init__(f"git {' '.join(command)} failed: {stderr.strip()}" if found else "git not found in PATH")


@dataclass(frozen=True)
class Git:
    folder: Path | None = None
    """The repository git acts on; None for the current directory."""
    env: Mapping[str, str] | None = None
    """The whole environment git runs in; None for this process's."""

    def output(self, *args: str, input: str | None = None) -> str:
        result = self._text(args, input, capture=True)
        if result.returncode != 0:
            raise GitError(args, result.stderr)
        return result.stdout

    def output_bytes(self, *args: str, input: bytes | None = None) -> bytes:
        result = self._bytes(args, input, capture=True)
        if result.returncode != 0:
            raise GitError(args, result.stderr.decode(errors="replace"))
        return result.stdout

    def result(self, *args: str, input: str | None = None) -> subprocess.CompletedProcess[str]:
        return self._text(args, input, capture=True)

    def succeeds(self, *args: str, input: str | bytes | None = None, show_output: bool = False) -> bool:
        """Whether the command exits 0. With ``show_output``, git writes straight to this process's stdout and
        stderr, after what this process has already written there; otherwise its output is discarded."""
        if show_output:
            sys.stdout.flush()
            sys.stderr.flush()
        if isinstance(input, bytes):
            return self._bytes(args, input, capture=not show_output).returncode == 0
        return self._text(args, input, capture=not show_output).returncode == 0

    def current_branch(self) -> str:
        """The branch checked out, or "detached"."""
        result = self.result("symbolic-ref", "--short", "HEAD")
        return result.stdout.strip() if result.returncode == 0 else "detached"

    def _text(self, args: Sequence[str], input: str | None, *, capture: bool) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                self._argv(args), input=input, capture_output=capture, text=True, env=self._env(), check=False
            )
        except FileNotFoundError:
            raise GitError(args, "", found=False) from None

    def _bytes(self, args: Sequence[str], input: bytes | None, *, capture: bool) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(self._argv(args), input=input, capture_output=capture, env=self._env(), check=False)
        except FileNotFoundError:
            raise GitError(args, "", found=False) from None

    def _argv(self, args: Sequence[str]) -> list[str]:
        folder = ["-C", str(self.folder)] if self.folder is not None else []
        return ["git", *folder, *args]

    def _env(self) -> dict[str, str] | None:
        return dict(self.env) if self.env is not None else None
