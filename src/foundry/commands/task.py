"""foundry task create: a new task on a project, ready for foundry run."""

import argparse

from foundry import config, paths, task
from foundry.github import GhCli, repo_slug_from_url


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create tasks on projects")
    actions = parser.add_subparsers(dest="action", required=True)
    create = actions.add_parser(
        "create",
        help="create task/TASK from the default branch, and .agent/TASK/ on agent-notes from config/task-template/",
        description="Uses the GitHub CLI (gh), signed in as you. Refuses a task that already exists.",
    )
    create.add_argument("project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml")
    create.add_argument("task_id", metavar="TASK", help="task id, e.g. WCF-0042")
    create.set_defaults(func=create_main)


def create_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, task template and GitHub."""
    foundry_root = paths.find_foundry_root()
    project = config.load(paths.config_path(foundry_root)).project(args.project_name)
    template = task.load_template(paths.task_template_dir(foundry_root))
    task.create(GhCli(), repo_slug_from_url(project.url), args.task_id, template)
    print("\n".join(report(project.name, args.task_id)))
    return 0


def report(project_name: str, task_id: str) -> list[str]:
    return [f"created task {task_id} in {project_name}", f"run it with: foundry run {project_name} ROLE {task_id}"]
