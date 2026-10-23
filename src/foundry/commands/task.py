"""foundry task create: a new task on a project, ready for foundry run."""

import argparse
from pathlib import Path

from foundry import config, paths, task
from foundry.errors import FoundryError
from foundry.github import GhCli, repo_slug_from_url


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create tasks on projects")
    actions = parser.add_subparsers(dest="action", required=True)
    create = actions.add_parser(
        "create",
        help="create task/TASK from the default branch, with FILE as its TASK.md on agent-notes (created if missing)",
        description="Uses the GitHub CLI (gh), signed in as you. Refuses a task that already exists.",
    )
    create.add_argument("project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
    create.add_argument("task_id", metavar="TASK", help="task id, e.g. WCF-0042")
    create.add_argument("task_md_path", metavar="FILE", type=Path, help="the task's TASK.md")
    create.set_defaults(func=create_main)


def create_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and GitHub."""
    foundry_config = config.load(paths.config_path(paths.find_foundry_root()))
    project = foundry_config.project(args.project_name)
    try:
        task_md = args.task_md_path.read_text()
    except FileNotFoundError:
        raise FoundryError(f"{args.task_md_path} is missing") from None
    task.create(GhCli(), repo_slug_from_url(project.url), args.task_id, task_md)
    print("\n".join(report(project.name, args.task_id)))
    return 0


def report(project_name: str, task_id: str) -> list[str]:
    return [f"created task {task_id} in {project_name}", f"run it with: foundry run {project_name} ROLE {task_id}"]
