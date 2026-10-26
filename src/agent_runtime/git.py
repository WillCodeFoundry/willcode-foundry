"""git, as the runtime runs it to read a repository: output captured as text, failure left to the caller."""

import subprocess
from pathlib import Path


def run(
    *args: str, cwd: Path | None = None, input: str | None = None, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """``git *args`` in ``cwd`` (this process's directory by default), its output captured.

    ``check`` raises CalledProcessError on failure; otherwise the caller reads the return code.
    """
    return subprocess.run(["git", *args], cwd=cwd, input=input, capture_output=True, text=True, check=check)


def current_branch(cwd: Path | None = None) -> str:
    """The branch checked out in ``cwd``'s repository, or "detached"."""
    result = run("symbolic-ref", "--short", "HEAD", cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else "detached"
