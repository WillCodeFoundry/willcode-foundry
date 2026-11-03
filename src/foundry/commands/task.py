"""foundry task: create a task on a project, ready for foundry run, close and reopen it, and list whose turn each is."""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from agent_runtime.git import GitError
from foundry import config, paths, task
from foundry.config import Config, Project
from foundry.errors import FoundryError
from foundry.project_tasks import ProjectTasks, TaskSummary


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create, close, reopen and list tasks on projects")
    actions = parser.add_subparsers(dest="action", required=True)
    # The arguments every action takes.
    task_arguments = argparse.ArgumentParser(add_help=False)
    task_arguments.add_argument(
        "project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml"
    )
    task_arguments.add_argument("task_id", metavar="TASK", help="task id, e.g. wcf-0042")
    create = actions.add_parser(
        "create",
        parents=[task_arguments],
        help=f"create task/TASK from the default branch, and {task.OPEN_DIR}/TASK/ on {task.NOTES_BRANCH} "
        "from config/task-template/",
        description="Uses git, with your own access to the project's repository. "
        "Refuses a task that already exists, open or closed.",
    )
    create.set_defaults(func=create_main)
    close = actions.add_parser(
        "close",
        parents=[task_arguments],
        help=f"move {task.OPEN_DIR}/TASK/ to {task.CLOSED_DIR}/TASK/ on {task.NOTES_BRANCH}",
        description="Uses git, with your own access to the project's repository. Changes nothing else: not the "
        "task's branch, its sandboxes or its sessions. Refuses a task that is closed or doesn't exist.",
    )
    close.set_defaults(func=close_main)
    reopen = actions.add_parser(
        "reopen",
        parents=[task_arguments],
        help=f"move {task.CLOSED_DIR}/TASK/ back to {task.OPEN_DIR}/TASK/ on {task.NOTES_BRANCH}",
        description="Uses git, with your own access to the project's repository. Refuses a task that is open or "
        "doesn't exist.",
    )
    reopen.set_defaults(func=reopen_main)
    list_parser = actions.add_parser(
        "list",
        help=f"list the open tasks and whose turn each is, from {task.TURN_FILE} on {task.NOTES_BRANCH}",
        description="Uses git, with your own access to each project's repository, and changes nothing. Lists the "
        "tasks of the named projects, or of every project in config/foundry.yaml. Exits 1 if any project can't "
        "be listed, after listing the others.",
    )
    list_parser.add_argument(
        "project_names", metavar="PROJECT", nargs="*", help="project names (default: every project)"
    )
    list_parser.add_argument(
        "--turn", metavar="ROLE", help=f"only the tasks whose {task.TURN_FILE} is ROLE: human for those waiting for you"
    )
    list_parser.set_defaults(func=list_main)


def create_main(args: argparse.Namespace) -> int:
    """Composition root: the real config, task template and repository, in a scratch clone."""
    foundry_root = paths.find_foundry_root()
    project = config.load(foundry_root).project(args.project_name)
    template = task.load_template(paths.task_template_dir(foundry_root))
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as project_tasks:
        created = project_tasks.create_task(args.task_id, template)
    print("\n".join(report(CREATED, project.name, created)))
    return 0


def close_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as project_tasks:
        closed = project_tasks.close_task(args.task_id)
    print("\n".join(report(CLOSED, project.name, closed)))
    return 0


def reopen_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as project_tasks:
        reopened = project_tasks.reopen_task(args.task_id)
    print("\n".join(report(REOPENED, project.name, reopened)))
    return 0


def list_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repositories, each in a scratch clone; exit 1 if any failed."""
    projects = list_projects(config.load(paths.find_foundry_root()), args.project_names)
    listings = [list_project(project, os.environ) for project in projects]
    stdout, stderr = listing_lines(listings, args.turn)
    if stdout:
        print("\n".join(stdout))
    if stderr:
        print("\n".join(stderr), file=sys.stderr)
    return 1 if stderr else 0


class Outcome(NamedTuple):
    """What an action did to the task, and what you do next."""

    past_tense: str
    next_command: str


CREATED = Outcome("created", "run it with: foundry run")
CLOSED = Outcome("closed", "reopen it with: foundry task reopen")
REOPENED = Outcome("reopened", "run it with: foundry run")


def report(outcome: Outcome, project_name: str, changed: task.Task) -> list[str]:
    return [
        f"{outcome.past_tense} task {changed.id} in {project_name}",
        f"{outcome.next_command} {project_name} {changed.id}",
    ]


class ProjectListing(NamedTuple):
    """What listing one project gave: its open tasks, or the reason it couldn't be listed."""

    project_name: str
    summaries: list[TaskSummary]
    error: str | None


def list_projects(foundry_config: Config, project_names: Sequence[str]) -> list[Project]:
    """The projects to list, in name order: those named, each once, or all. FoundryError for an unknown name."""
    return [foundry_config.project(name) for name in sorted(set(project_names) or foundry_config.projects)]


def list_project(project: Project, env: Mapping[str, str]) -> ProjectListing:
    """``project``'s open tasks, through a scratch clone; a failure is the listing's error, so the rest can go on.

    ``env`` is the environment git runs in, as for ProjectClone.
    """
    try:
        with ProjectTasks.in_scratch_clone(project.url, env) as project_tasks:
            return ProjectListing(project.name, project_tasks.list_open_task_summaries(), None)
    except (FoundryError, GitError) as error:
        return ProjectListing(project.name, [], str(error))


def listing_lines(listings: Sequence[ProjectListing], turn: str | None) -> tuple[list[str], list[str]]:
    """The lines list prints on stdout and on stderr.

    A task line is its project, id and turn, in columns as wide as the widest across every task line. A project
    with nothing to show gets a line outside the columns, and a failed one an error line. ``turn``, when given,
    keeps only the tasks whose turn it equals.
    """
    listed = [(listing, _with_turn(listing.summaries, turn)) for listing in listings if listing.error is None]
    name_width = max((len(listing.project_name) for listing, shown in listed if shown), default=0)
    id_width = max((len(summary.task.id) for _, shown in listed for summary in shown), default=0)
    stdout = []
    for listing, shown in listed:
        if shown:
            stdout += [f"{listing.project_name:<{name_width}}  {s.task.id:<{id_width}}  {s.turn}" for s in shown]
        elif not listing.summaries:
            stdout.append(f"{listing.project_name}  no open tasks")
        else:
            stdout.append(f"{listing.project_name}  no open tasks with turn {turn}")
    stderr = [f"error: {listing.project_name}: {listing.error}" for listing in listings if listing.error is not None]
    return stdout, stderr


def _with_turn(summaries: Sequence[TaskSummary], turn: str | None) -> list[TaskSummary]:
    """The summaries whose turn is ``turn``, or all of them when it is None."""
    return [summary for summary in summaries if turn is None or summary.turn == turn]
