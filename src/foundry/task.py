"""Tasks on a project's repository: a task/<id> branch, and .agent/<id>/ on agent-notes, from a template."""

from collections.abc import Mapping
from pathlib import Path

from foundry import session
from foundry.errors import FoundryError
from foundry.git_clone import REMOTE_NAME, GitClone

AGENT_NOTES_BRANCH = "agent-notes"


def load_template(template_dir: Path) -> dict[str, str]:
    """Every file directly in ``template_dir``, by name: what a new task's .agent/<id>/ starts with."""
    try:
        return {path.name: path.read_text() for path in sorted(template_dir.iterdir()) if path.is_file()}
    except FileNotFoundError:
        raise FoundryError(f"{template_dir} is missing") from None


def create(clone: GitClone, task_id: str, template: Mapping[str, str]) -> None:
    """Create task/<id> from the default branch and copy ``template`` into .agent/<id>/ on agent-notes.

    Both branches are pushed at once, so either both change or neither does. Refuses if the task
    exists. agent-notes is created for the first task, as an orphan branch: it shares no history
    with the code.
    """
    session.require_valid_task_id(task_id)
    task_branch = f"task/{task_id}"
    notes_path = f".agent/{task_id}"
    default_branch = clone.default_branch()
    branches = clone.branches()
    if task_branch in branches:
        raise FoundryError(f"task {task_id} already exists: there is a {task_branch} branch")
    if default_branch is None or default_branch not in branches:  # a repository with no commits yet
        raise FoundryError(f"the repository has no commits to branch {task_branch} from")

    if AGENT_NOTES_BRANCH in branches:
        clone.fetch(AGENT_NOTES_BRANCH)
        clone.switch(AGENT_NOTES_BRANCH)
    else:
        clone.switch_orphan(AGENT_NOTES_BRANCH)
    notes_dir = clone.work_dir / notes_path
    try:
        notes_dir.mkdir(parents=True)
    except FileExistsError:
        raise FoundryError(f"task {task_id} already exists: {AGENT_NOTES_BRANCH} has {notes_path}/") from None
    for name, text in template.items():
        (notes_dir / name).write_text(text)
    clone.commit(notes_path, f"Add task {task_id}")
    clone.fetch(default_branch)
    clone.push_atomic({task_branch: f"{REMOTE_NAME}/{default_branch}", AGENT_NOTES_BRANCH: AGENT_NOTES_BRANCH})
