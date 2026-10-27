"""The agent kit's copied skills, and merging upstream's changes into them.

A copied skill is a folder in agent-kit/skills/ whose SKILL.md has a metadata.source: the upstream repo, the
skill's path there, and the commit it's up to date with. Updating one applies upstream's changes since that
commit, without agents/, with git's three-way merge, and records the new commit. A line both sides changed is
left as a merge conflict, to review (git diff HEAD), resolve and commit.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from agent_runtime.agent_kit import AgentKit
from agent_runtime.git import Git
from foundry import paths
from foundry.errors import FoundryError


def github_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


@dataclass(frozen=True)
class Source:
    """A SKILL.md's metadata.source: where the skill was copied from."""

    repo: str
    path: str
    commit: str

    @property
    def licence_name(self) -> str:
        """The file beside the skills holding the repository's licence: one per repository."""
        return f"LICENSE-{self.repo.replace('/', '-')}"


def update(
    foundry_root: Path,
    ref: str = "HEAD",
    url_for: Callable[[str], str] = github_url,
    report: Callable[[str], None] = lambda line: None,
) -> list[str]:
    """Update every copied skill in the foundry's agent kit to ``ref`` of its upstream repository, and return
    the skills git couldn't merge cleanly, whose files hold conflict markers.

    Runs git in ``foundry_root``, which must be a git checkout: upstream's commits are fetched into it. Each
    repository's ``ref`` is resolved once, so its skills all reach the same commit. A copied skill with
    uncommitted changes stops the run before anything changes. Each skill's outcome goes to ``report`` as soon
    as it is known. A skill whose patch git rejects outright keeps its commit, and the run raises FoundryError
    at the end, naming it and any conflicted skills.
    """
    git = Git(foundry_root)
    agent_kit = AgentKit(paths.agent_kit_dir(foundry_root))
    copied = [
        (skill_md, source)
        for skill_md in sorted(agent_kit.skills.glob("*/SKILL.md"))
        if (source := read_source(skill_md))
    ]
    for skill_md, _ in copied:
        _refuse_uncommitted(git, skill_md.parent.relative_to(foundry_root))
    new_shas: dict[str, str] = {}
    conflicted: list[str] = []
    rejected: list[str] = []
    for skill_md, source in copied:
        name, url = skill_md.parent.name, url_for(source.repo)
        if source.repo not in new_shas:
            new_shas[source.repo] = _fetch(git, url, ref, into=f"refs/foundry/skills/{source.repo}")
        new_sha = new_shas[source.repo]
        if new_sha == source.commit:
            report(f"{name}: already at {source.commit[:12]}")
            continue
        outcome = _apply(git, _plan(git, foundry_root, url, skill_md, source, new_sha))
        if outcome == "rejected":
            rejected.append(name)
            report(f"{name}: rejected, still at {source.commit[:12]}")
        elif outcome == "conflicted":
            conflicted.append(name)
            report(f"{name}: conflicted at {new_sha[:12]}")
        else:
            report(f"{name}: updated to {new_sha[:12]}")
    if rejected:
        raise FoundryError(
            f"git apply rejected upstream's changes to {' '.join(rejected)}, which "
            f"{'stays at its commit' if len(rejected) == 1 else 'stay at their commits'}; "
            "see git's message above."
            + (
                f" Not merged cleanly: {' '.join(conflicted)}; resolve what git reported above, then commit"
                if conflicted
                else ""
            )
        )
    return conflicted


@dataclass(frozen=True)
class _Plan:
    """What updating one skill will write, everything read and checked: applying it reads nothing that can fail
    before it writes."""

    skill_md: Path
    skill_dir_in_repo: Path
    source: Source
    new_sha: str
    licence: bytes


def _plan(git: Git, foundry_root: Path, url: str, skill_md: Path, source: Source, new_sha: str) -> _Plan:
    """Every read and check for updating ``skill_md`` to ``new_sha``; writes nothing."""
    skill_md_text = skill_md.read_text()
    git.output("fetch", "--quiet", "--no-tags", url, source.commit)
    _require_one_commit_line(skill_md, skill_md_text, source.commit)
    # Byte for byte: whatever line endings and encoding upstream's licence has.
    licence = git.output_bytes("show", f"{new_sha}:LICENSE")
    return _Plan(skill_md, skill_md.parent.relative_to(foundry_root), source, new_sha, licence)


def _apply(git: Git, plan: _Plan) -> Literal["updated", "conflicted", "rejected"]:
    """Write the plan: "updated", "conflicted" (conflict markers left, commit recorded), or "rejected" (nothing
    applied, nothing written)."""
    outcome: Literal["updated", "conflicted"] = "updated"
    if not _apply_upstream_changes(git, plan):
        if not git.output("ls-files", "--unmerged", "--", str(plan.skill_dir_in_repo)):
            return "rejected"
        outcome = "conflicted"
    plan.skill_md.write_text(_with_commit(plan.skill_md.read_text(), plan.source.commit, plan.new_sha))
    (plan.skill_md.parent.parent / plan.source.licence_name).write_bytes(plan.licence)
    return outcome


def _refuse_uncommitted(git: Git, skill_dir: Path) -> None:
    """git apply --3way checks against the index, so it would reject the whole patch rather than merge into a
    skill's uncommitted edits."""
    if git.output("status", "--porcelain", "--", str(skill_dir)):
        raise FoundryError(
            f"{skill_dir.name}: {skill_dir} has uncommitted changes; commit them, or stash them, then run again"
        )


def _fetch(git: Git, url: str, ref: str, *, into: str) -> str:
    """The SHA of ``ref`` at ``url``, fetched into the foundry's own ref ``into`` rather than FETCH_HEAD, which
    another fetch in the checkout, an editor's, say, could change meanwhile."""
    git.output("fetch", "--quiet", "--no-tags", url, f"+{ref}:{into}")
    return git.output("rev-parse", into).strip()


def read_source(skill_md: Path) -> Source | None:
    """The metadata.source of a SKILL.md's front matter, or None if it has none: one of the foundry's own."""
    text = skill_md.read_text()
    if not text.startswith("---"):
        return None
    try:
        # Every value as a string: a SHA of digits must not become a number.
        front = yaml.load(text.split("---", 2)[1], Loader=yaml.BaseLoader) or {}
    except yaml.YAMLError as error:
        raise FoundryError(f"{skill_md}: its front matter is not valid YAML: {error}") from None
    raw = front.get("metadata", {}).get("source") if isinstance(front.get("metadata"), dict) else None
    if raw is None:
        return None
    missing = [field for field in ("repo", "path", "commit") if not (isinstance(raw, dict) and raw.get(field))]
    if missing:
        raise FoundryError(f"{skill_md}: metadata.source has no {', '.join(missing)}")
    return Source(repo=raw["repo"], path=raw["path"], commit=raw["commit"])


def _apply_upstream_changes(git: Git, plan: _Plan) -> bool:
    """Apply upstream's diff of the skill's folder, without agents/ (Codex-only), with a three-way merge. False
    if git left conflicts or rejected the patch, which it reports as it goes."""
    path = plan.source.path
    pathspec = [path, f":(exclude){path}/agents"]
    diff = git.output_bytes("diff", "--binary", plan.source.commit, plan.new_sha, f"--relative={path}", "--", *pathspec)
    return git.run_visibly("apply", "--3way", "--allow-empty", f"--directory={plan.skill_dir_in_repo}", input=diff)


def _commit_line(old: str) -> re.Pattern[str]:
    return re.compile(rf"^(    commit:[ \t]*){re.escape(old)}[ \t]*$", flags=re.MULTILINE)


def _require_one_commit_line(skill_md: Path, text: str, old: str) -> None:
    """The line recording ``old`` is there once, for _with_commit to rewrite."""
    if (count := len(_commit_line(old).findall(text))) != 1:
        raise FoundryError(f"{skill_md}: found {count} lines recording commit {old[:12]}; expected one")


def _with_commit(text: str, old: str, new: str) -> str:
    """``text`` with ``new`` recorded in place of ``old``, the rest of the file as it was."""
    return _commit_line(old).sub(rf"\g<1>{new}", text)
