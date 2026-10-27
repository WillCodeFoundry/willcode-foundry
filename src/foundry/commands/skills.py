"""foundry skills update: merge upstream's changes into the agent kit's copied skills. Run by hand."""

import argparse
import sys

from foundry import paths, skills


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
        "ref", metavar="COMMIT", nargs="?", default="HEAD", help="upstream commit to update to (default: latest)"
    )
    update_parser.set_defaults(func=update_main)


def update_main(args: argparse.Namespace) -> int:
    """Composition root: this foundry's skills, against their upstream repositories on GitHub."""
    conflicted = skills.update(paths.find_foundry_root(), args.ref, report=lambda line: print(line, flush=True))
    if conflicted:
        print(
            f"skills update: not merged cleanly: {' '.join(conflicted)}; resolve what git reported above, then commit",
            file=sys.stderr,
        )
        return 1
    return 0
