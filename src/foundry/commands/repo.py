"""foundry repo check: how each project's repository deviates from the repo policy, and --fix for its rulesets."""

import argparse
from typing import NamedTuple

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
    foundry_config = config.load(paths.config_path(foundry_root))
    policy = repo_policy.load(paths.repo_policy_dir(foundry_root))
    github = GhCli()

    all_conform = True
    for project_name in args.project_names or sorted(foundry_config.projects):
        project = check_one_project(foundry_config, policy, github, project_name, fix=args.fix)
        print("\n".join(report(project)))
        all_conform = all_conform and project.result.conforms
    return 0 if all_conform else 1


class CheckedProject(NamedTuple):
    name: str
    repo_slug: str | None
    """None when the project's URL isn't a GitHub repository's; the result says why."""
    result: ProjectCheck


def check_one_project(
    foundry_config: Config, policy: RepoPolicy, github: GitHub, project_name: str, *, fix: bool
) -> CheckedProject:
    """Check one project's repository; a URL that isn't GitHub's is part of the result, like a GitHub error.

    Raises FoundryError for a project config/foundry.yaml doesn't list.
    """
    project = foundry_config.project(project_name)
    try:
        repo_slug = repo_slug_from_url(project.url)
    except FoundryError as error:
        return CheckedProject(project_name, None, ProjectCheck([], [], error=str(error)))
    return CheckedProject(project_name, repo_slug, repo_policy.check_project(github, repo_slug, policy, fix=fix))


def report(project: CheckedProject) -> list[str]:
    """The lines check prints for one project: its header, what --fix changed, then its error, 'conforms', or
    each deviation's diff."""
    result = project.result
    lines = [project.name if project.repo_slug is None else f"{project.name} ({project.repo_slug})"]
    lines += [f"  {change.action:<8} ruleset {change.ruleset_name}" for change in result.changes]
    if result.error is not None:
        return [*lines, f"  error    {result.error}"]
    if not result.deviations:
        lines.append("  conforms")
    for deviation in result.deviations:
        lines.append(f"  differs  {deviation.subject}")
        lines += [f"           {line}" for line in deviation.diff.splitlines()]
    return lines
