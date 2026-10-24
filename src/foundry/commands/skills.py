"""foundry skills update: reinstall the agent kit's copied skills from skills.lock."""

import argparse
import os
import tempfile
from pathlib import Path

from foundry import paths, skills
from foundry.git_clone import GitClone


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("skills", help="manage the agent kit's copied skills")
    actions = parser.add_subparsers(dest="action", required=True)
    update = actions.add_parser(
        "update",
        help=f"reinstall the agent kit's copied skills from agent-kit/skills/{skills.LOCK_FILE}",
        description=f"Fetches the commit {skills.LOCK_FILE} pins, with git and your own access, copies each skill "
        f"it lists into agent-kit/skills/, applies the foundry's patch for it from {skills.PATCHES_DIR}/, and "
        "writes its attribution. Nothing is changed if any skill can't be installed. Review the result with git, "
        "then commit it.",
    )
    update.set_defaults(func=update_main)


def update_main(args: argparse.Namespace) -> int:
    """Composition root: the real lock and skills folder, and the source repository in a scratch clone."""
    foundry_root = paths.find_foundry_root()
    skills_dir = paths.skills_dir(foundry_root)
    lock = skills.load_lock(skills_dir / skills.LOCK_FILE)
    with tempfile.TemporaryDirectory(prefix="foundry-skills-source-") as scratch_dir:
        clone = GitClone.init(lock.repo, Path(scratch_dir), os.environ)
        clone.check_out_commit(lock.commit)
        installed = skills.install(lock, Path(scratch_dir), skills_dir)
    print("\n".join(report(lock, installed)))
    return 0


def report(lock: skills.Lock, installed: list[str]) -> list[str]:
    return [
        f"installed {', '.join(installed)} from {lock.repo_slug} at {lock.commit[:12]}",
        "review the changes with: git status agent-kit/skills, then commit them",
    ]
