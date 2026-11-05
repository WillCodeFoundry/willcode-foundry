"""foundry task: create a task on a project, ready for foundry run, close and reopen it, hand it off, and list
whose turn each is."""

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
    parser = subparsers.add_parser("task", help="create, close, reopen, hand off and list tasks on projects")
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
    handoff = actions.add_parser(
        "handoff",
        parents=[task_arguments],
        help=f"write ROLE to the open task's {task.TURN_FILE} on {task.NOTES_BRANCH}, "
        f"and say so in its {task.LOG_FILE}",
        description="Uses git, with your own access to the project's repository, and one commit signed with your "
        f"key. Refuses a task that is closed or doesn't exist, whose turn is already ROLE, or that has no "
        f"{task.LOG_FILE}. Starts nothing: run the role with foundry run.",
    )
    handoff.add_argument("turn", metavar="ROLE", help=f"role name, as listed in config/foundry.yaml, or {task.HUMAN}")
    handoff.add_argument("--note", metavar="TEXT", help=f"one line to add to the {task.LOG_FILE} entry")
    handoff.set_defaults(func=handoff_main)
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
    with ProjectTasks.in_scratch_clone(project, os.environ) as project_tasks:
        created = project_tasks.create_task(args.task_id, template)
    print("\n".join(report(CREATED, project.name, created)))
    return 0


def close_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    with ProjectTasks.in_scratch_clone(project, os.environ) as project_tasks:
        closed = project_tasks.close_task(args.task_id)
    print("\n".join(report(CLOSED, project.name, closed)))
    return 0


def reopen_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    with ProjectTasks.in_scratch_clone(project, os.environ) as project_tasks:
        reopened = project_tasks.reopen_task(args.task_id)
    print("\n".join(report(REOPENED, project.name, reopened)))
    return 0


def handoff_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    foundry_config = config.load(paths.find_foundry_root())
    project = foundry_config.project(args.project_name)
    require_valid_handoff_args(foundry_config, task_id=args.task_id, turn=args.turn, note=args.note)
    with ProjectTasks.in_scratch_clone(project, os.environ) as project_tasks:
        before = project_tasks.handoff(args.task_id, args.turn, note=args.note)
    print("\n".join(handoff_lines(project.name, args.task_id, before=before, after=args.turn)))
    return 0


def list_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repositories, each in a scratch clone; exit 1 if any failed."""
    projects = chosen_projects(config.load(paths.find_foundry_root()), args.project_names)
    listings, errors = read_listings_and_errors(projects, os.environ)
    stdout, stderr = listing_lines([filter_project_listing(listing, args.turn) for listing in listings], errors)
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


def require_valid_handoff_args(foundry_config: Config, *, task_id: str, turn: str, note: str | None) -> None:
    """Refuse a handoff's arguments that don't check out, so none reaches git.

    FoundryError for an invalid task id, a ``turn`` that is neither a role in ``foundry_config`` nor HUMAN, or a
    ``note`` that is blank or more than one line.
    """
    task.Task.as_open(task_id)  # refuses an invalid id as create does
    if turn != task.HUMAN and turn not in foundry_config.roles:
        known = ", ".join(sorted(foundry_config.roles)) or "none"
        raise FoundryError(f"{turn!r} is not a role; known: {known}, or {task.HUMAN}")
    if note is not None and not note.strip():
        raise FoundryError("--note is empty: give it text, or leave it out")
    if note is not None and note.splitlines() != [note]:
        raise FoundryError("--note holds a line break: give it one line")


def handoff_lines(project_name: str, task_id: str, *, before: str, after: str) -> list[str]:
    """What handoff prints: the handoff, then how to run the task, unless it now waits for you."""
    lines = [f"task {task_id} in {project_name}: handoff {before} → {after}"]
    if after != task.HUMAN:
        lines.append(f"run it with: foundry run {project_name} {task_id}")
    return lines


class ProjectListing(NamedTuple):
    """A project's open tasks. ``no_tasks_note`` is what the project's line says when it shows no task."""

    project_name: str
    summaries: list[TaskSummary]
    no_tasks_note: str = "no open tasks"


def chosen_projects(foundry_config: Config, project_names: Sequence[str]) -> list[Project]:
    """The projects to list, in name order: those named, each once, or all. FoundryError for an unknown name."""
    return [foundry_config.project(name) for name in sorted(set(project_names) or foundry_config.projects)]


def read_project_listing(project: Project, env: Mapping[str, str]) -> ProjectListing:
    """``project``'s open tasks, through a scratch clone.

    ``env`` is the environment git runs in, as for ProjectClone.
    """
    with ProjectTasks.in_scratch_clone(project, env) as project_tasks:
        return ProjectListing(project.name, project_tasks.list_open_task_summaries())


def read_listings_and_errors(
    projects: Sequence[Project], env: Mapping[str, str]
) -> tuple[list[ProjectListing], list[FoundryError]]:
    """The listing of each project that could be listed, and an error for each that couldn't.

    Each error is a FoundryError that names its project. Both lists keep ``projects``' order. One project's failure
    doesn't stop the rest.
    """
    listings: list[ProjectListing] = []
    errors: list[FoundryError] = []
    for project in projects:
        try:
            listings.append(read_project_listing(project, env))
        except (FoundryError, GitError) as error:
            errors.append(FoundryError(f"{project.name}: {error}"))
    return listings, errors


def filter_project_listing(listing: ProjectListing, turn: str | None) -> ProjectListing:
    """A new listing of ``listing``'s project with only the tasks whose turn is ``turn``.

    When it had tasks but none match, its note says so. When ``turn`` is None, no --turn was given, and
    ``listing`` itself is returned.
    """
    if turn is None:
        return listing
    return ProjectListing(
        project_name=listing.project_name,
        summaries=[summary for summary in listing.summaries if summary.turn == turn],
        no_tasks_note=f"no open tasks with turn {turn}" if listing.summaries else listing.no_tasks_note,
    )


def listing_lines(listings: Sequence[ProjectListing], errors: Sequence[FoundryError]) -> tuple[list[str], list[str]]:
    """The lines list prints on stdout and on stderr.

    A task line is its project, id and turn, in columns as wide as the widest across every task line. A project
    with no task gets its note, outside the columns. Each error is an error line.
    """
    name_width = max((len(listing.project_name) for listing in listings if listing.summaries), default=0)
    id_width = max((len(summary.task.id) for listing in listings for summary in listing.summaries), default=0)
    stdout = []
    for listing in listings:
        if listing.summaries:
            stdout += [
                f"{listing.project_name:<{name_width}}  {s.task.id:<{id_width}}  {s.turn}" for s in listing.summaries
            ]
        else:
            stdout.append(f"{listing.project_name}  {listing.no_tasks_note}")
    stderr = [f"error: {error}" for error in errors]
    return stdout, stderr
