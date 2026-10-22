"""foundry protect: check, or apply, the GitHub rulesets each project's repository must have."""

import argparse
from collections.abc import Callable

from foundry import config, paths, protection
from foundry.errors import FoundryError
from foundry.github import GitHub, GitHubError, repo_slug

PROTECTION_FILE_HELP = "config/github-protection.yaml"


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "protect",
        help="check or apply the GitHub rulesets projects must have",
        description=(
            f"Compare each project's GitHub rulesets with {PROTECTION_FILE_HELP}, or make them match. "
            "Uses the GitHub CLI (gh), signed in as you."
        ),
    )
    actions = parser.add_subparsers(dest="action", required=True)

    check = actions.add_parser("check", help="report what is missing or differs; exit 1 if anything does")
    check.add_argument("project_names", metavar="PROJECT", nargs="*", help="projects to check (default: all)")
    check.set_defaults(func=check_main)

    apply = actions.add_parser("apply", help="create missing rulesets and update ones that differ")
    apply.add_argument("project_names", metavar="PROJECT", nargs="*", help="projects to apply to (default: all)")
    apply.add_argument("--dry-run", action="store_true", help="show what would change without changing it")
    apply.set_defaults(func=apply_main)


def check_main(args: argparse.Namespace, agent_args: tuple[str, ...]) -> int:
    return _for_each_repo(args, agent_args, GitHub(), _report)


def apply_main(args: argparse.Namespace, agent_args: tuple[str, ...]) -> int:
    def apply_repo(github: GitHub, status: protection.RepoStatus) -> bool:
        if status.rulesets_match:
            return _report(github, status)
        for ruleset_status in status.rulesets:
            if ruleset_status.state is protection.RulesetState.OK:
                continue
            verb = "create" if ruleset_status.state is protection.RulesetState.MISSING else "update"
            if args.dry_run:
                print(f"  would {verb} {ruleset_status.ruleset_name}")
                _print_differences(ruleset_status)
            else:
                protection.apply_status(github, status.repo_slug, ruleset_status)
                print(f"  {verb + 'd':<8} {ruleset_status.ruleset_name}")
        _print_file_checks(status)
        _print_unmanaged(status)
        return status.files_ok and not args.dry_run  # a dry run leaves it unprotected

    return _for_each_repo(args, agent_args, GitHub(), apply_repo)


def _for_each_repo(
    args: argparse.Namespace,
    agent_args: tuple[str, ...],
    github: GitHub,
    handle: Callable[[GitHub, protection.RepoStatus], bool],
) -> int:
    """Run ``handle`` on each selected project's status; exit 1 unless every one ends up protected.

    ``handle`` returns whether the repository is protected once it is done.
    """
    if agent_args:
        raise FoundryError("foundry protect takes no arguments after '--'")
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(paths.config_path(foundry_root))
    rulesets = protection.load(paths.github_protection_path(foundry_root))
    project_names = args.project_names or sorted(foundry_config.projects)

    all_ok = True
    for project_name in project_names:
        project = foundry_config.project(project_name)
        slug = repo_slug(project.url)
        print(f"{project_name} ({slug})")
        try:
            protected = handle(github, protection.check_repo(github, slug, rulesets))
        except GitHubError as error:
            print(f"  error    {error}")
            protected = False
        all_ok = all_ok and protected
    return 0 if all_ok else 1


def _report(github: GitHub, status: protection.RepoStatus) -> bool:
    for ruleset_status in status.rulesets:
        print(f"  {ruleset_status.state:<8} {ruleset_status.ruleset_name}")
        _print_differences(ruleset_status)
    _print_file_checks(status)
    _print_unmanaged(status)
    return status.is_protected


def _print_differences(status: protection.RulesetStatus) -> None:
    for difference in status.differences:
        print(f"           {difference}")


def _print_file_checks(status: protection.RepoStatus) -> None:
    for check in status.file_checks:
        state = "ok" if check.ok else "missing"
        print(f"  {state:<8} {check.description}: {check.detail}")
    if not status.files_ok:
        print("           fix these in the project; apply does not change project files")


def _print_unmanaged(status: protection.RepoStatus) -> None:
    if status.unmanaged_ruleset_names:
        print(f"  also on GitHub, left alone: {', '.join(status.unmanaged_ruleset_names)}")
