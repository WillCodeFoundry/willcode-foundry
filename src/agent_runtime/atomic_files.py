"""Replacing a file or a link in one step: written beside it under a fresh name, then renamed over it.

A reader that already has the old file open keeps reading all of it, and nobody sees half a file. The fresh
name comes from mkstemp, which never opens an existing path, so a link placed beside the target can't catch
the write; the rename replaces a link at the target itself rather than writing through it.
"""

import os
import tempfile
from pathlib import Path


def atomic_write(target: Path, content: bytes, *, mode: int = 0o644, owner: tuple[int, int] | None = None) -> None:
    """Make ``target`` hold ``content``, with ``mode`` and, when given, ``owner`` as (uid, gid)."""
    descriptor, partial_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    partial = Path(partial_name)
    try:
        with os.fdopen(descriptor, "wb") as partial_file:
            partial_file.write(content)
        if owner is not None:
            os.chown(partial, *owner)
        partial.chmod(mode)
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)


def atomic_symlink(link: Path, target: Path, *, owner: tuple[int, int] | None = None) -> None:
    """Make ``link`` a symbolic link to ``target``, whatever was there before."""
    for attempt in range(100):  # a fresh name, as mkstemp picks one, but for a link
        partial = link.with_name(f".{link.name}.{os.getpid()}.{attempt}")
        try:
            partial.symlink_to(target)
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError(f"no free name beside {link} for a new link")
    try:
        if owner is not None:
            os.lchown(partial, *owner)
        os.replace(partial, link)
    finally:
        partial.unlink(missing_ok=True)
