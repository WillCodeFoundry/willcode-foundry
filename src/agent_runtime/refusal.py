"""What the git hooks share, so every refusal has the same shape: what was wrong, then what to do instead."""

import sys
from typing import NoReturn


def refuse(hook: str, *lines: str) -> NoReturn:
    """Print a refusal that says what was wrong and what to do instead, then exit non-zero."""
    body = "".join(f"  {line}\n" for line in lines)
    sys.stderr.write(f"{hook}: refusing\n\n{body}\n")
    sys.exit(1)
