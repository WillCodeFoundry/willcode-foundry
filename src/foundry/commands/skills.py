"""foundry skills update: merge upstream's changes into the agent kit's copied skills. Run by hand.

A copied skill is a folder in agent-kit/skills/ whose SKILL.md has a metadata.source: the upstream repo, the
skill's path there, and the commit it's up to date with. For each, this applies upstream's changes since that
commit, without agents/, with git's three-way merge, and records the new commit. A line both sides changed is
left as a merge conflict. Then review (git diff HEAD), resolve, and commit.
"""

import argparse
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agent_runtime.agent_kit import AgentKit
from agent_runtime.git import Git
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
    repository's ``commit`` is resolved once, so its skills all reach the same commit. A copied skill with
    uncommitted changes stops the run before anything changes. Each skill's line, already up to date or
    updated to which commit, goes to ``report`` as soon as it is done, so a failure from a later skill, a
    GitError or a FoundryError, doesn't hide what earlier ones changed on disk.
    """
    git = Git(foundry_root)
    skills_dir = AgentKit(paths.agent_kit_dir(foundry_root)).skills
    copied = [
        (skill_md, source)
        for skill_md in sorted(skills_dir.glob("*/SKILL.md"))
        if (source := read_source(skill_md)) is not None  # None: one of the foundry's own skills
    ]
    for skill_md, _ in copied:
        _refuse_uncommitted(git, skill_md.parent.relative_to(foundry_root))
    resolved: dict[str, str] = {}
    conflicted: list[str] = []
    for skill_md, source in copied:
        skill_dir = skill_md.parent
        if source.repo not in resolved:
            resolved[source.repo] = _fetch(git, url_for(source.repo), commit, source.repo)
        new = resolved[source.repo]
        if new == source.commit:
            report(f"{skill_dir.name}: already at {source.commit[:12]}")
            continue
        git.output("fetch", "--quiet", "--no-tags", url_for(source.repo), source.commit)
        # Read before anything is written: a missing licence stops the skill with nothing changed.
        license_bytes = git.output_bytes("show", f"{new}:LICENSE")
        updated_skill_md = _with_commit(skill_md, source.commit, new)
        if not _apply_upstream_changes(git, source, new, skill_dir.relative_to(foundry_root)):
            if not git.output("ls-files", "--unmerged", "--", str(skill_dir)):
                raise FoundryError(
                    f"{skill_dir.name}: git apply rejected upstream's changes; see git's message above. "
                    f"Nothing was applied, and its commit stays {source.commit[:12]}"
                )
            conflicted.append(skill_dir.name)
        skill_md.write_text(updated_skill_md(skill_md.read_text()))
        # Byte for byte: whatever line endings and encoding upstream's licence has.
        (skills_dir / f"LICENSE-{source.repo.replace('/', '-')}").write_bytes(license_bytes)
        report(f"{skill_dir.name}: updated to {new[:12]}")
    return conflicted


def _refuse_uncommitted(git: Git, skill_dir: Path) -> None:
    """git apply --3way checks against the index, so it would reject the whole patch rather than merge into a
    skill's uncommitted edits."""
    if git.output("status", "--porcelain", "--", str(skill_dir)):
        raise FoundryError(
            f"{skill_dir.name}: {skill_dir} has uncommitted changes; commit them, or stash them, then run again"
        )


def _fetch(git: Git, url: str, commit: str, repo: str) -> str:
    """``commit`` of the repository at ``url``, fetched into a ref of the foundry's own, not FETCH_HEAD, which
    another fetch in the checkout, an editor's, say, could change meanwhile."""
    ref = f"refs/foundry/skills/{repo}"
    git.output("fetch", "--quiet", "--no-tags", url, f"+{commit}:{ref}")
    return git.output("rev-parse", ref).strip()


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


def _apply_upstream_changes(git: Git, source: Source, new: str, skill_dir: Path) -> bool:
    """Apply upstream's diff of the skill's folder, without agents/ (Codex-only), with a three-way merge, into
    ``skill_dir``, relative to the repository. False if git left conflicts, which it reports as it goes."""
    pathspec = [source.path, f":(exclude){source.path}/agents"]
    diff = git.output_bytes("diff", "--binary", source.commit, new, f"--relative={source.path}", "--", *pathspec)
    return git.succeeds("apply", "--3way", "--allow-empty", f"--directory={skill_dir}", input=diff, show_output=True)


def _with_commit(skill_md: Path, old: str, new: str) -> Callable[[str], str]:
    """What records ``new`` in place of ``old`` in a SKILL.md's text: checked against the file as it is now, so a
    commit line it can't find stops the skill before upstream's changes are applied."""
    pattern = re.compile(rf"^(    commit:[ \t]*){re.escape(old)}[ \t]*$", flags=re.MULTILINE)

    def rewrite(text: str) -> str:
        rewritten, count = pattern.subn(rf"\g<1>{new}", text)
        if count != 1:
            raise FoundryError(f"{skill_md}: found {count} lines recording commit {old[:12]}; expected one")
        return rewritten

    rewrite(skill_md.read_text())
    return rewrite
