"""foundry protect: compare each project's repository with the project standard, or apply its rulesets."""

import argparse
from collections.abc import Callable

from foundry import config, paths, standard
from foundry.errors import FoundryError
from foundry.github import GitHub, GitHubError, repo_slug

STANDARD_HELP = "config/project-standard/"


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "protect",
        help="check projects against the project standard, or apply its rulesets",
        description=(
            f"Compare each project's GitHub rulesets, CODEOWNERS and ci.yml with {STANDARD_HELP}, "
            "or create and update the rulesets to match. Uses the GitHub CLI (gh), signed in as you."
        ),
    )
    actions = parser.add_subparsers(dest="action", required=True)
    for name, help_text, func in (
        ("check", "show what differs from the standard; exit 1 if anything does", check_main),
        ("apply", "make the rulesets match, then check; project files are shown, never written", apply_main),
    ):
        action = actions.add_parser(name, help=help_text)
        action.add_argument("project_names", metavar="PROJECT", nargs="*", help="projects (default: all)")
        action.set_defaults(func=func)


def check_main(args: argparse.Namespace, agent_args: tuple[str, ...]) -> int:
    return _for_each_repo(args, agent_args, lambda github, slug, project_standard: None)


def apply_main(args: argparse.Namespace, agent_args: tuple[str, ...]) -> int:
    def apply_rulesets(github: GitHub, slug: str, project_standard: standard.Standard) -> None:
        actual_rulesets = github.rulesets(slug)
        for ruleset in project_standard.rulesets:
            actual = actual_rulesets.get(ruleset["name"])
            if actual is None:
                github.api("POST", f"repos/{slug}/rulesets", ruleset)
                print(f"  created  ruleset {ruleset['name']}")
            elif standard.compare("", standard.project(actual, ruleset), ruleset).diff:
                github.api("PUT", f"repos/{slug}/rulesets/{actual['id']}", ruleset)
                print(f"  updated  ruleset {ruleset['name']}")

    return _for_each_repo(args, agent_args, apply_rulesets)


def _for_each_repo(
    args: argparse.Namespace,
    agent_args: tuple[str, ...],
    before_check: Callable[[GitHub, str, standard.Standard], None],
) -> int:
    """For each selected project, run ``before_check``, then check and report; exit 1 unless all match."""
    if agent_args:
        raise FoundryError("foundry protect takes no arguments after '--'")
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(paths.config_path(foundry_root))
    project_standard = standard.load(paths.project_standard_path(foundry_root))
    github = GitHub()

    all_match = True
    for project_name in args.project_names or sorted(foundry_config.projects):
        slug = repo_slug(foundry_config.project(project_name).url)
        print(f"{project_name} ({slug})")
        try:
            before_check(github, slug, project_standard)
            findings = standard.check(github, slug, project_standard)
        except GitHubError as error:
            print(f"  error    {error}")
            all_match = False
            continue
        for finding in findings:
            print(f"  {'differs' if finding.diff else 'ok':<8} {finding.subject}")
            for line in finding.diff.splitlines():
                print(f"           {line}")
        all_match = all_match and not any(finding.diff for finding in findings)
    return 0 if all_match else 1
