"""git, as the runtime runs it to read a repository: output captured as text, failure left to the caller.

A command for another repository than the current directory's names it with git's own ``-C``: unlike a
subprocess working directory, a missing one is a git failure the caller reads, not an exception.
"""

import subprocess


def run(*args: str, input: str | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    """``git *args``, its output captured.

    ``check`` raises CalledProcessError on failure; otherwise the caller reads the return code.
    """
    return subprocess.run(["git", *args], input=input, capture_output=True, text=True, check=check)


def current_branch() -> str:
    """The branch checked out in the current directory's repository, where git runs its hooks, or "detached"."""
    result = run("symbolic-ref", "--short", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else "detached"
