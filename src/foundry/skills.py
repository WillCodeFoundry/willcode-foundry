"""The agent kit's copied skills: reading skills.lock, and installing each skill it lists from a checkout of
the source repository into agent-kit/skills/, with the foundry's patch for it and its attribution.

A copied skill is one whose SKILL.md frontmatter has a metadata.source; the foundry's own skills
(git-conventions) have none, and installing never overwrites them.
"""

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

import yaml

from foundry import yaml_io
from foundry.errors import FoundryError

# The lock file in agent-kit/skills/: the source repository, its commit, and each skill's folder in it.
LOCK_FILE: Final = "skills.lock"
# The folder in agent-kit/skills/ holding the foundry's changes to each copied skill, as <name>.patch.
PATCHES_DIR: Final = "patches"
# Left out of every copied skill: Codex-only metadata.
_LEFT_OUT: Final = ("agents",)
# Named in each adapted skill's metadata.
_ADAPTED_FOR: Final = "willcode-foundry"

_COMMIT = re.compile(r"[0-9a-f]{40}")
# A skill name is its folder in agent-kit/skills/, so a single plain folder name.
_SKILL_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
_SOURCE_KEYS: Final = ("repo", "commit", "license", "author", "license_name")
_FRONTMATTER = re.compile(r"\A---\n(.*?\n)?---\n", re.DOTALL)


@dataclass(frozen=True)
class Lock:
    """skills.lock: the source repository, the commit to copy from, and each skill's folder in it.

    ``license`` is the source's licence file, relative to its root; ``author`` and ``license_name`` go
    into each skill's attribution.
    """

    repo: str
    commit: str
    license: str
    author: str
    license_name: str
    skills: Mapping[str, str]
    """Skill name -> its folder in the source repository, relative to its root."""

    @property
    def repo_slug(self) -> str:
        """``owner/name``: from https://github.com/owner/name.git, git@github.com:owner/name.git, or a path."""
        parts = re.split(r"[/:]", self.repo.removesuffix("/").removesuffix(".git"))
        return "/".join(parts[-2:])

    @property
    def license_copy(self) -> str:
        """The licence's file name in agent-kit/skills/: LICENSE-<owner>."""
        return f"LICENSE-{self.repo_slug.partition('/')[0]}"


def load_lock(lock_path: Path) -> Lock:
    """Read and check skills.lock; a malformed one is refused, naming the file and the problem."""
    raw = yaml_io.load(lock_path)

    def refuse(problem: str) -> FoundryError:
        return FoundryError(f"{lock_path}: {problem}")

    if not isinstance(raw, dict) or set(raw) != {"source", "skills"}:
        raise refuse("must be a mapping with source and skills, and nothing else")
    source, skill_entries = raw["source"], raw["skills"]
    if not isinstance(source, dict) or set(source) != set(_SOURCE_KEYS):
        raise refuse(f"source must have exactly {', '.join(_SOURCE_KEYS)}")
    for key in _SOURCE_KEYS:
        if not isinstance(source[key], str) or not source[key]:
            raise refuse(f"source.{key} must be text")
    if not _COMMIT.fullmatch(source["commit"]):
        raise refuse("source.commit must be a full 40-character commit id, so the copy is pinned")
    if not _relative(source["license"]):
        raise refuse("source.license must be a relative path inside the source repository")
    if not isinstance(skill_entries, dict) or not skill_entries:
        raise refuse("skills must map at least one skill name to {path: <folder in the source repository>}")

    skill_paths: dict[str, str] = {}
    for name, entry in skill_entries.items():
        if not isinstance(name, str) or not _SKILL_NAME.fullmatch(name) or name == PATCHES_DIR:
            raise refuse(f"{name!r} is not a valid skill name: lowercase letters, digits, '-' and '_'")
        if not isinstance(entry, dict) or set(entry) != {"path"} or not isinstance(entry["path"], str):
            raise refuse(f"skills.{name} must be {{path: <folder in the source repository>}}")
        if not _relative(entry["path"]):
            raise refuse(f"skills.{name}.path must be a relative path inside the source repository")
        skill_paths[name] = entry["path"]

    return Lock(
        repo=source["repo"],
        commit=source["commit"],
        license=source["license"],
        author=source["author"],
        license_name=source["license_name"],
        skills=skill_paths,
    )


def install(lock: Lock, source_dir: Path, skills_dir: Path) -> list[str]:
    """Install every skill in ``lock`` from ``source_dir``, a checkout of the source at its commit, into
    ``skills_dir``; return their names, in the lock's order.

    Each is copied without ``agents/``, patched with ``skills_dir/patches/<name>.patch`` if there is one, and
    given its attribution in its frontmatter's metadata. Every skill is prepared before any is replaced, so a
    skill that can't be (a patch that doesn't apply, one of the foundry's own skills in the way, something
    missing from the source) leaves ``skills_dir`` unchanged. Replacing a skill's folder removes files dropped
    upstream. The source's licence is copied last, as ``lock.license_copy``.
    """
    license_path = source_dir / lock.license
    if not license_path.is_file():
        raise FoundryError(f"the source has no {lock.license} at {lock.commit}")
    with tempfile.TemporaryDirectory(prefix="foundry-skills-") as staging:
        staging_dir = Path(staging)
        for name, path in lock.skills.items():
            try:
                _refuse_foundrys_own(skills_dir / name)
                _prepare(lock, name, path, source_dir, skills_dir, staging_dir / name)
            except FoundryError as error:
                raise FoundryError(f"skill {name}: {error}") from None
        for name in lock.skills:
            shutil.rmtree(skills_dir / name, ignore_errors=True)
            shutil.copytree(staging_dir / name, skills_dir / name)
    shutil.copyfile(license_path, skills_dir / lock.license_copy)
    return list(lock.skills)


def source_metadata(skill_md: str) -> object:
    """The metadata.source in a SKILL.md's frontmatter, or None: what marks a skill as copied."""
    metadata = _split(skill_md)[0].get("metadata")
    return metadata.get("source") if isinstance(metadata, dict) else None


def _refuse_foundrys_own(installed_dir: Path) -> None:
    if not installed_dir.exists():
        return
    skill_md = installed_dir / "SKILL.md"
    try:
        copied = skill_md.is_file() and source_metadata(skill_md.read_text()) is not None
    except FoundryError:
        copied = False
    if not copied:
        raise FoundryError(
            f"{installed_dir} has no metadata.source in its SKILL.md: it is one of the foundry's own skills, "
            "which are never overwritten; rename the copied skill in skills.lock"
        )


def _prepare(lock: Lock, name: str, path: str, source_dir: Path, skills_dir: Path, staged_dir: Path) -> None:
    """Write the installed form of one skill into ``staged_dir``."""
    upstream_dir = source_dir / path
    if not (upstream_dir / "SKILL.md").is_file():
        raise FoundryError(f"the source's {path} has no SKILL.md at {lock.commit}")
    shutil.copytree(upstream_dir, staged_dir, ignore=shutil.ignore_patterns(*_LEFT_OUT))

    patch_path = skills_dir / PATCHES_DIR / f"{name}.patch"
    if patch_path.is_file():
        _apply(patch_path, staged_dir, f"{PATCHES_DIR}/{name}.patch")

    skill_md = staged_dir / "SKILL.md"
    attribution: dict[str, Any] = {
        "source": {
            "repo": lock.repo_slug,
            "path": path,
            "commit": lock.commit,
            "author": lock.author,
            "license": f"{lock.license_name} (see ../{lock.license_copy})",
        }
    }
    if patch_path.is_file():
        attribution["adapted"] = f"for {_ADAPTED_FOR}; changes in ../{PATCHES_DIR}/{name}.patch"
    skill_md.write_text(_with_metadata(skill_md.read_text(), attribution))


def _apply(patch_path: Path, skill_dir: Path, patch_name: str) -> None:
    """Apply a patch whose paths are relative to the skill's folder (a/SKILL.md)."""
    # git apply in a folder that isn't a repository patches files relative to it; the ceiling stops git
    # finding a repository the temporary folder happens to sit in.
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(skill_dir.parent)}
    try:
        result = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(patch_path.resolve())],
            cwd=skill_dir,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        raise FoundryError("git not found in PATH") from None
    if result.returncode != 0:
        raise FoundryError(f"{patch_name} does not apply: {result.stderr.strip()}")


def _with_metadata(skill_md: str, attribution: Mapping[str, Any]) -> str:
    """``skill_md`` with ``attribution``'s keys set in its frontmatter's metadata, keeping the others."""
    frontmatter, body = _split(skill_md)
    metadata = frontmatter.get("metadata")
    frontmatter["metadata"] = {**(metadata if isinstance(metadata, dict) else {}), **attribution}
    dumped = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, width=1_000_000)
    return f"---\n{dumped}---\n{body}"


def _split(skill_md: str) -> tuple[dict[str, Any], str]:
    """A SKILL.md's frontmatter, as a mapping, and the rest of the file."""
    match = _FRONTMATTER.match(skill_md)
    if not match:
        raise FoundryError("its SKILL.md has no frontmatter between --- lines")
    try:
        frontmatter = yaml.safe_load(match[1] or "") or {}
    except yaml.YAMLError as error:
        raise FoundryError(f"its SKILL.md's frontmatter is not valid YAML: {error}") from None
    if not isinstance(frontmatter, dict):
        raise FoundryError("its SKILL.md's frontmatter is not a mapping")
    return frontmatter, skill_md[match.end() :]


def _relative(path: str) -> bool:
    pure = PurePosixPath(path)
    return bool(path) and not pure.is_absolute() and ".." not in pure.parts
