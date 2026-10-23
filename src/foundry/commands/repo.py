"""foundry repo check: how each project's repository deviates from the repo policy, and --fix for what it can."""

import argparse

from foundry import config, paths, repo_policy
from foundry.github import GhCli, GitHubError, repo_slug_from_url
from foundry.repo_policy import Change, Deviation


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "repo",
        help="check projects' GitHub repositories against the repo policy",
        description=(
            "Compare each project's rulesets, agent-notes branch, CODEOWNERS and ci.yml with config/repo-policy/. "
            "Uses the GitHub CLI (gh), signed in as you."
        ),
    )
    actions = parser.add_subparsers(dest="action", required=True)
    check = actions.add_parser(
        "check", help="report how each project's repository deviates from the repo policy; exit 1 if any do"
    )
    check.add_argument("project_names", metavar="PROJECT", nargs="*", help="projects (default: all)")
    check.add_argument(
        "--fix",
        action="store_true",
        help="first create agent-notes if missing and create or update the rulesets; project files are never written",
    )
    check.set_defaults(func=check_main)


def check_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, policy and GitHub; exit 0 only if every project conforms."""
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(paths.config_path(foundry_root))
    policy = repo_policy.load(paths.repo_policy_dir(foundry_root))
    github = GhCli()

    all_conform = True
    for project_name in args.project_names or sorted(foundry_config.projects):
        repo_slug = repo_slug_from_url(foundry_config.project(project_name).url)
        try:
            changes = repo_policy.fix(github, repo_slug, policy) if args.fix else []
            deviations = repo_policy.deviations(github, repo_slug, policy)
        except GitHubError as error:
            print(f"{project_name} ({repo_slug})\n  error    {error}")
            all_conform = False
            continue
        print("\n".join(report(project_name, repo_slug, changes, deviations)))
        all_conform = all_conform and not deviations
    return 0 if all_conform else 1


def report(project_name: str, repo_slug: str, changes: list[Change], deviations: list[Deviation]) -> list[str]:
    """The lines check prints for one project: what --fix changed, then 'conforms' or each deviation's diff."""
    lines = [f"{project_name} ({repo_slug})"]
    lines += [f"  {change.action:<8} {change.subject}" for change in changes]
    if not deviations:
        lines.append("  conforms")
    for deviation in deviations:
        lines.append(f"  differs  {deviation.subject}")
        lines += [f"           {line}" for line in deviation.diff.splitlines()]
    return lines
