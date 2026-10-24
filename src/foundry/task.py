"""Tasks on a project's repository: a task/<id> branch, and .agent/<id>/ on agent-notes, from a template."""

from collections.abc import Mapping
from pathlib import Path

from foundry import session
from foundry.errors import FoundryError
from foundry.git_remote import GitRemote

AGENT_NOTES_BRANCH = "agent-notes"


def load_template(template_dir: Path) -> dict[str, str]:
    """Every file directly in ``template_dir``, by name: what a new task's .agent/<id>/ starts with."""
    try:
        return {path.name: path.read_text() for path in sorted(template_dir.iterdir()) if path.is_file()}
    except FileNotFoundError:
        raise FoundryError(f"{template_dir} is missing") from None


def create(remote: GitRemote, task_id: str, template: Mapping[str, str]) -> None:
    """Create task/<id> from the default branch and copy ``template`` into .agent/<id>/ on agent-notes.

    Both branches are pushed at once, so either both change or neither does. Refuses if the task
    exists. agent-notes is created for the first task, as an orphan branch: it shares no history
    with the code.
    """
    session.require_valid_task_id(task_id)
    task_branch = f"task/{task_id}"
    notes_dir = f".agent/{task_id}"
    default_branch = remote.default_branch()
    branch_heads = remote.branch_heads()
    if task_branch in branch_heads:
        raise FoundryError(f"task {task_id} already exists: there is a {task_branch} branch")
    if default_branch is None or default_branch not in branch_heads:  # a repository with no commits yet
        raise FoundryError(f"the repository has no commits to branch {task_branch} from")

    base_sha = remote.fetch_commit(default_branch)
    notes_sha = remote.fetch_tree(AGENT_NOTES_BRANCH) if AGENT_NOTES_BRANCH in branch_heads else None
    if notes_sha is not None and remote.paths(notes_sha, notes_dir):
        raise FoundryError(f"task {task_id} already exists: {AGENT_NOTES_BRANCH} has {notes_dir}/")
    files = {f"{notes_dir}/{name}": text for name, text in template.items()}
    commit_sha = remote.commit_files(files, f"Add task {task_id}", parent_sha=notes_sha)
    remote.push_atomic({task_branch: base_sha, AGENT_NOTES_BRANCH: commit_sha})
