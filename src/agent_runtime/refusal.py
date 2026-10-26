"""What the git hooks share, so every refusal has the same shape: what was wrong, then what to do instead."""

import subprocess
import sys
from typing import NoReturn


def refuse(hook: str, *lines: str) -> NoReturn:
    """Print a refusal that says what was wrong and what to do instead, then exit non-zero."""
    body = "".join(f"  {line}\n" for line in lines)
    sys.stderr.write(f"{hook}: refusing\n\n{body}\n")
    sys.exit(1)


def current_branch() -> str:
    """The branch checked out in the current directory's repository, or "detached"."""
    result = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "detached"
