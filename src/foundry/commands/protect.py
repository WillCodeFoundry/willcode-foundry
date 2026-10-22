"""foundry protect: compare each project's repository with the repo policy, or apply its rulesets."""

import argparse
from collections.abc import Callable

from foundry import config, paths, repo_policy
from foundry.github import GitHub, GitHubError, repo_slug_from_url


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "protect",
        help="check projects against the repo policy, or apply its rulesets",
        description=(
            "Compare each project's GitHub rulesets, CODEOWNERS and ci.yml with config/repo-policy/, "
            "or create and update the rulesets to match. Uses the GitHub CLI (gh), signed in as you."
        ),
    )
    actions = parser.add_subparsers(dest="action", required=True)
    for name, help_text, func in (
        ("check", "show how projects deviate from the repo policy; exit 1 if any do", check_main),
        ("apply", "make the rulesets match, then check; project files are shown, never written", apply_main),
    ):
        action = actions.add_parser(name, help=help_text)
        action.add_argument("project_names", metavar="PROJECT", nargs="*", help="projects (default: all)")
        action.set_defaults(func=func)


def check_main(args: argparse.Namespace) -> int:
    return _for_each_repo(args, lambda github, repo_slug, policy: None)


def apply_main(args: argparse.Namespace) -> int:
    def apply_rulesets(github: GitHub, repo_slug: str, policy: repo_policy.RepoPolicy) -> None:
        actual_rulesets = github.rulesets(repo_slug)
        for ruleset in policy.rulesets:
            actual = actual_rulesets.get(ruleset["name"])
            if actual is None:
                github.api("POST", f"repos/{repo_slug}/rulesets", ruleset)
                print(f"  created  ruleset {ruleset['name']}")
            elif repo_policy.compare("", repo_policy.restrict_to(ruleset, actual), ruleset) is not None:
                github.api("PUT", f"repos/{repo_slug}/rulesets/{actual['id']}", ruleset)
                print(f"  updated  ruleset {ruleset['name']}")

    return _for_each_repo(args, apply_rulesets)


def _for_each_repo(
    args: argparse.Namespace,
    before_check: Callable[[GitHub, str, repo_policy.RepoPolicy], None],
) -> int:
    """For each selected project, run ``before_check``, then check and report; exit 1 unless all conform."""
    foundry_root = paths.find_foundry_root()
    foundry_config = config.load(paths.config_path(foundry_root))
    policy = repo_policy.load(paths.repo_policy_dir(foundry_root))
    github = GitHub()

    all_conform = True
    for project_name in args.project_names or sorted(foundry_config.projects):
        repo_slug = repo_slug_from_url(foundry_config.project(project_name).url)
        print(f"{project_name} ({repo_slug})")
        try:
            before_check(github, repo_slug, policy)
            deviations = repo_policy.deviations(github, repo_slug, policy)
        except GitHubError as error:
            print(f"  error    {error}")
            all_conform = False
            continue
        if not deviations:
            print("  conforms")
        for deviation in deviations:
            print(f"  differs  {deviation.subject}")
            for line in deviation.diff.splitlines():
                print(f"           {line}")
        all_conform = all_conform and not deviations
    return 0 if all_conform else 1
