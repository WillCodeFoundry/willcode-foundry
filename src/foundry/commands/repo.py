"""foundry repo check [--fix]: each project's repository has agent-notes and matches the repo policy."""

import argparse

from foundry import config, paths, repo_policy, task
from foundry.github import GhCli, GitHubError, repo_slug_from_url


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "repo",
        help="check projects' GitHub repositories: agent-notes, and the repo policy",
        description=(
            "Check each project's repository has an agent-notes branch, and compare its rulesets, CODEOWNERS and "
            "ci.yml with config/repo-policy/. Uses the GitHub CLI (gh), signed in as you."
        ),
    )
    actions = parser.add_subparsers(dest="action", required=True)
    check = actions.add_parser(
        "check", help="report a missing agent-notes and each deviation from the repo policy; exit 1 if any"
    )
    check.add_argument("project_names", metavar="PROJECT", nargs="*", help="projects (default: all)")
    check.add_argument(
        "--fix",
        action="store_true",
        help="first create agent-notes if missing, and create or update the rulesets; project files are never written",
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
            notes_created = task.ensure_notes_branch(github, repo_slug) if args.fix else False
            changes = repo_policy.apply_rulesets(github, repo_slug, policy) if args.fix else []
            notes_missing = not task.has_notes_branch(github, repo_slug)
            deviations = repo_policy.deviations(github, repo_slug, policy)
        except GitHubError as error:
            print(f"{project_name} ({repo_slug})\n  error    {error}")
            all_conform = False
            continue
        print("\n".join(report(project_name, repo_slug, changes, deviations, notes_created, notes_missing)))
        all_conform = all_conform and not deviations and not notes_missing
    return 0 if all_conform else 1


def report(
    project_name: str,
    repo_slug: str,
    changes: list[repo_policy.RulesetChange],
    deviations: list[repo_policy.Deviation],
    notes_created: bool,
    notes_missing: bool,
) -> list[str]:
    """The lines check prints for one project: what --fix did, then 'conforms', or what's missing or deviates."""
    lines = [f"{project_name} ({repo_slug})"]
    if notes_created:
        lines.append(f"  created  branch {task.NOTES_BRANCH}")
    lines += [f"  {change.action:<8} ruleset {change.ruleset_name}" for change in changes]
    if notes_missing:
        lines.append(f"  missing  branch {task.NOTES_BRANCH}")
    if not deviations and not notes_missing:
        lines.append("  conforms")
    for deviation in deviations:
        lines.append(f"  differs  {deviation.subject}")
        lines += [f"           {line}" for line in deviation.diff.splitlines()]
    return lines
