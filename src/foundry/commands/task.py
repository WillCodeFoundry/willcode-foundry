"""foundry task: create a task on a project, ready for foundry run, close and reopen it, hand it off, show what one
waits for, and list whose turn each is."""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from agent_runtime.git import GitError
from foundry import config, paths, task
from foundry.config import Config, Project
from foundry.errors import FoundryError
from foundry.project_tasks import ProjectTasks, TaskTurn, TaskTurnAndLog, last_log_entry


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("task", help="create, close, reopen, hand off, show and list tasks on projects")
    actions = parser.add_subparsers(dest="action", required=True)
    # The arguments every action on one task takes: its project, then the task, which create alone may leave out.
    project_argument = argparse.ArgumentParser(add_help=False)
    project_argument.add_argument(
        "project_name", metavar="PROJECT", help="project name, as listed in config/foundry.yaml"
    )
    task_arguments = argparse.ArgumentParser(add_help=False, parents=[project_argument])
    task_arguments.add_argument("task_id", metavar="TASK", help="task id, e.g. wcf-0042")
    create = actions.add_parser(
        "create",
        parents=[project_argument],
        help=f"create task/TASK from the default branch, and {task.OPEN_DIR}/TASK/ on {task.NOTES_BRANCH} "
        "from config/task-template/",
        description="Uses git, with your own access to the project's repository. "
        "Refuses a task that already exists, open or closed. Without TASK, refuses when the project has no task id "
        "yet, or when task prefixes tie for the most task ids.",
    )
    create.add_argument(
        "task_id",
        metavar="TASK",
        nargs="?",
        help="task id, e.g. wcf-0042 (default: the next id with the task prefix most of the project's task ids use; "
        "ids with other task prefixes are ignored)",
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
    show = actions.add_parser(
        "show",
        parents=[task_arguments],
        help=f"show whose turn the task is, and the last entry of its {task.LOG_FILE} on {task.NOTES_BRANCH}",
        description="Uses git, with your own access to the project's repository, and changes nothing. Shows an open "
        f"or closed task. Refuses one whose {task.TURN_FILE} or {task.LOG_FILE} is missing, a link or not a file, "
        f"or whose {task.TURN_FILE} is empty.",
    )
    show.set_defaults(func=show_main)
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
    template = task.load_task_template(paths.task_template_dir(foundry_root))
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as project_tasks:
        created = project_tasks.create_task(task_id_to_create(project_tasks, args.task_id), template)
    print("\n".join(report(CREATED, project.name, created)))
    return 0


def task_id_to_create(project_tasks: ProjectTasks, task_id: str | None) -> str:
    """The id of the task create makes: ``task_id`` as given, even when not valid, or, when it is None, the next."""
    return task_id if task_id is not None else pick_next_task_id(project_tasks)


def pick_next_task_id(project_tasks: ProjectTasks) -> str:
    """The project's next task id, from the ids its tasks and task branches take.

    When none can be picked, the FoundryError says to give TASK.
    """
    try:
        return task.next_task_id(project_tasks.taken_task_ids())
    except task.NoNextTaskIdError as error:
        raise FoundryError(f"{error}. Give TASK to say which task to create.") from error


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


def handoff_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    foundry_config = config.load(paths.find_foundry_root())
    project = foundry_config.project(args.project_name)
    require_valid_handoff_args(foundry_config, task_id=args.task_id, turn=args.turn, note=args.note)
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as project_tasks:
        project_tasks.hand_off(args.task_id, args.turn, note=args.note)
    print("\n".join(handoff_lines(project.name, args.task_id, turn=args.turn)))
    return 0


def show_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repository, in a scratch clone."""
    project = config.load(paths.find_foundry_root()).project(args.project_name)
    task.Task.as_open(args.task_id)  # refuses an invalid id as create does, before any git
    with ProjectTasks.in_scratch_clone(project.url, os.environ) as project_tasks:
        turn_and_log = project_tasks.fetch_task_turn_and_log(args.task_id)
    print("\n".join(show_lines(turn_and_log)))
    return 0


def list_main(args: argparse.Namespace) -> int:
    """Composition root: the real config and repositories, each in a scratch clone; exit 1 if any failed."""
    projects = chosen_projects(config.load(paths.find_foundry_root()), args.project_names)
    listings, errors = read_listings_and_errors(projects, os.environ)
    stdout_lines, stderr_lines = listing_lines(
        [filter_project_listing(listing, args.turn) for listing in listings], errors
    )
    if stdout_lines:
        print("\n".join(stdout_lines))
    if stderr_lines:
        print("\n".join(stderr_lines), file=sys.stderr)
    return 1 if stderr_lines else 0


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


def handoff_lines(project_name: str, task_id: str, *, turn: str) -> list[str]:
    """What handoff prints: the handoff, then how to run the task, unless it now waits for you."""
    lines = [f"task {task_id} in {project_name}: handoff to {turn}"]
    if turn != task.HUMAN:
        lines.append(f"run it with: foundry run {project_name} {task_id}")
    return lines


def show_lines(turn_and_log: TaskTurnAndLog) -> list[str]:
    """What show prints: a status line if the task is closed, its turn, a blank line, then its log's last entry."""
    status_lines = ["status: closed"] if turn_and_log.task.status is task.Status.CLOSED else []
    entry = last_log_entry(turn_and_log.log) or "no log entry yet"
    return [*status_lines, f"turn: {turn_and_log.turn}", "", entry]


class ProjectListing(NamedTuple):
    """A project's open tasks. ``no_tasks_note`` is what the project's line says when it shows no task."""

    project_name: str
    task_turns: list[TaskTurn]
    no_tasks_note: str = "no open tasks"


def chosen_projects(foundry_config: Config, project_names: Sequence[str]) -> list[Project]:
    """The projects to list, in name order: those named, each once, or all. FoundryError for an unknown name."""
    return [foundry_config.project(name) for name in sorted(set(project_names) or foundry_config.projects)]


def read_project_listing(project: Project, env: Mapping[str, str]) -> ProjectListing:
    """``project``'s open tasks, through a scratch clone.

    ``env`` is the environment git runs in, as for ProjectScratchClone.
    """
    with ProjectTasks.in_scratch_clone(project.url, env) as project_tasks:
        return ProjectListing(project.name, project_tasks.fetch_open_task_turns())


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
        task_turns=[task_turn for task_turn in listing.task_turns if task_turn.turn == turn],
        no_tasks_note=f"no open tasks with turn {turn}" if listing.task_turns else listing.no_tasks_note,
    )


def listing_lines(listings: Sequence[ProjectListing], errors: Sequence[FoundryError]) -> tuple[list[str], list[str]]:
    """The lines list prints on stdout and on stderr.

    A task line is its project, id and turn, in columns as wide as the widest across every task line. A project
    with no task gets its note, outside the columns. Each error is an error line.
    """
    name_width = max((len(listing.project_name) for listing in listings if listing.task_turns), default=0)
    id_width = max((len(task_turn.task.id) for listing in listings for task_turn in listing.task_turns), default=0)
    stdout_lines = []
    for listing in listings:
        if listing.task_turns:
            stdout_lines += [
                f"{listing.project_name:<{name_width}}  {task_turn.task.id:<{id_width}}  {task_turn.turn}"
                for task_turn in listing.task_turns
            ]
        else:
            stdout_lines.append(f"{listing.project_name}  {listing.no_tasks_note}")
    stderr_lines = [f"error: {error}" for error in errors]
    return stdout_lines, stderr_lines
