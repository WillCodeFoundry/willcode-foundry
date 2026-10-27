"""foundry skills update: merge upstream's changes into the agent kit's copied skills. Run by hand.

A copied skill is a folder in agent-kit/skills/ whose SKILL.md has a metadata.source: the upstream repo, the
skill's path there, and the commit it's up to date with. For each, this applies upstream's changes since that
commit, without agents/, with git's three-way merge, and records the new commit. A line both sides changed is
left as a merge conflict. Then review (git diff HEAD), resolve, and commit.
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agent_runtime.agent_kit import AgentKit
from foundry import paths
from foundry.errors import FoundryError


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("skills", help="maintain the agent kit's skills")
    actions = parser.add_subparsers(dest="action", required=True)
    update_parser = actions.add_parser(
        "update",
        help="merge upstream's changes into the agent kit's copied skills",
        description=(
            "For each skill copied from upstream, apply upstream's changes since its recorded commit with git's "
            "three-way merge, and record the new commit. Review with git diff HEAD, resolve conflicts, and commit."
        ),
    )
    update_parser.add_argument(
        "commit", metavar="COMMIT", nargs="?", default="HEAD", help="upstream commit to update to (default: latest)"
    )
    update_parser.set_defaults(func=update_main)


def update_main(args: argparse.Namespace) -> int:
    """Composition root: this foundry's skills, against their upstream repositories on GitHub."""
    conflicted = update(paths.find_foundry_root(), args.commit, report=lambda line: print(line, flush=True))
    if conflicted:
        print(
            f"skills update: not merged cleanly: {' '.join(conflicted)}; resolve what git reported above, then commit",
            file=sys.stderr,
        )
        return 1
    return 0


def github_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


@dataclass(frozen=True)
class Source:
    """A SKILL.md's metadata.source: where the skill was copied from."""

    repo: str
    path: str
    commit: str


def update(
    foundry_root: Path,
    commit: str = "HEAD",
    url_for: Callable[[str], str] = github_url,
    report: Callable[[str], None] = lambda line: None,
) -> list[str]:
    """Update every copied skill in the foundry's agent kit to ``commit`` of its upstream repository, and
    return the skills git couldn't merge cleanly, whose files hold conflict markers.

    Runs git in ``foundry_root``, which must be a git checkout: upstream's commits are fetched into it. Each
    skill's line, already up to date or updated to which commit, goes to ``report`` as soon as it is done, so
    a FoundryError from a later skill doesn't hide what earlier ones changed on disk.
    """
    conflicted: list[str] = []

    skills_dir = AgentKit(paths.agent_kit_dir(foundry_root)).skills
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        source = read_source(skill_md)
        if source is None:
            continue  # one of the foundry's own skills
        skill_dir = skill_md.parent
        url = url_for(source.repo)
        _git(foundry_root, "fetch", "--quiet", "--no-tags", url, commit)
        new = _git(foundry_root, "rev-parse", "FETCH_HEAD").strip()
        if new == source.commit:
            report(f"{skill_dir.name}: already at {source.commit[:12]}")
            continue
        _git(foundry_root, "fetch", "--quiet", "--no-tags", url, source.commit)
        if not _apply_upstream_changes(foundry_root, source, new, skill_dir):
            conflicted.append(skill_dir.name)
        skill_md.write_text(_with_commit(skill_md.read_text(), source.commit, new))
        # Byte for byte: whatever line endings and encoding upstream's licence has.
        license_bytes = _git_bytes(foundry_root, "show", f"{new}:LICENSE")
        (skills_dir / f"LICENSE-{source.repo.partition('/')[0]}").write_bytes(license_bytes)
        report(f"{skill_dir.name}: updated to {new[:12]}")
    return conflicted


def read_source(skill_md: Path) -> Source | None:
    """The metadata.source block of a SKILL.md's frontmatter, or None if it has none.

    Read line by line, as it is written: ``  source:`` under ``metadata:``, its fields indented by four.
    """
    fields: dict[str, str] = {}
    inside = False
    for line in skill_md.read_text().splitlines():
        if line.startswith("  source:"):
            inside = True
        elif inside:
            if not line.startswith("    "):
                break
            key, _, value = line.strip().partition(":")
            fields[key] = value.strip()
    if not fields.get("repo"):
        return None
    try:
        return Source(repo=fields["repo"], path=fields["path"], commit=fields["commit"])
    except KeyError as missing:
        raise FoundryError(f"{skill_md}: metadata.source has no {missing.args[0]}") from None


def _apply_upstream_changes(foundry_root: Path, source: Source, new: str, skill_dir: Path) -> bool:
    """Apply upstream's diff of the skill's folder, without agents/ (Codex-only), with a three-way merge.

    False if git left conflicts, which it reports on stderr.
    """
    pathspec = [source.path, f":(exclude){source.path}/agents"]
    diff = subprocess.run(
        ["git", "diff", "--binary", source.commit, new, f"--relative={source.path}", "--", *pathspec],
        cwd=foundry_root,
        capture_output=True,
        check=False,
    )
    if diff.returncode != 0:
        sys.stderr.write(diff.stderr.decode(errors="replace"))
        return False
    applied = subprocess.run(
        ["git", "apply", "--3way", "--allow-empty", f"--directory={skill_dir.relative_to(foundry_root)}"],
        cwd=foundry_root,
        input=diff.stdout,
        check=False,
    )
    return applied.returncode == 0


def _with_commit(skill_md_text: str, old: str, new: str) -> str:
    return re.sub(rf"^(    commit: ){re.escape(old)}$", rf"\g<1>{new}", skill_md_text, flags=re.MULTILINE)


def _git(cwd: Path, *args: str) -> str:
    return _git_bytes(cwd, *args).decode()


def _git_bytes(cwd: Path, *args: str) -> bytes:
    """git's output exactly as it wrote it; a failure is a FoundryError naming the command."""
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=False)
    if result.returncode != 0:
        raise FoundryError(f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout
