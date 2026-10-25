"""foundry repo check: how each project's repository deviates from the repo policy, and --fix for its rulesets."""

import argparse
from collections.abc import Callable

from foundry import config, paths, repo_policy
from foundry.config import Config
from foundry.errors import FoundryError
from foundry.github import GhCli, GitHub, repo_slug_from_url
from foundry.repo_policy import ProjectCheck, RepoPolicy


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "repo",
        help="check projects' GitHub repositories against the repo policy",
        description=(
            "Compare each project's GitHub rulesets, CODEOWNERS and ci.yml with config/repo-policy/. "
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
        help="first create or update the rulesets to match; project files are reported, never written",
    )
    check.set_defaults(func=check_main)


def check_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, policy and GitHub; exit 0 only if every project conforms."""
    foundry_root = paths.find_foundry_root()
    return check_projects(
        config.load(paths.config_path(foundry_root)),
        repo_policy.load(paths.repo_policy_dir(foundry_root)),
        GhCli(),
        args.project_names,
        fix=args.fix,
    )


def check_projects(
    foundry_config: Config,
    policy: RepoPolicy,
    github: GitHub,
    project_names: list[str],
    *,
    fix: bool,
    emit: Callable[[str], None] = print,
) -> int:
    """Check each project, named or all in name order, emitting its report as it goes; 0 only if all conform.

    A project's header is emitted before GitHub is asked about it, so a slow one shows which it is.
    A project that can't be checked is reported, and the rest are still checked.
    """
    all_conform = True
    for project_name in project_names or sorted(foundry_config.projects):
        project = foundry_config.project(project_name)
        try:
            repo_slug = repo_slug_from_url(project.url)
        except FoundryError as error:
            emit(project_name)
            emit(f"  error    {error}")
            all_conform = False
            continue
        emit(f"{project_name} ({repo_slug})")
        result = repo_policy.check_project(github, repo_slug, policy, fix=fix)
        for line in report(result):
            emit(line)
        all_conform = all_conform and result.conforms
    return 0 if all_conform else 1


def report(result: ProjectCheck) -> list[str]:
    """The lines under a project's header: what --fix changed, then its error, 'conforms', or each deviation's diff."""
    lines = [f"  {change.action:<8} ruleset {change.ruleset_name}" for change in result.changes]
    if result.error is not None:
        return [*lines, f"  error    {result.error}"]
    if not result.deviations:
        lines.append("  conforms")
    for deviation in result.deviations:
        lines.append(f"  differs  {deviation.subject}")
        lines += [f"           {line}" for line in deviation.diff.splitlines()]
    return lines
