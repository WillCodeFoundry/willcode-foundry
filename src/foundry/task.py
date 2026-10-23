"""Tasks on a project's GitHub repository: a task/<id> branch, and .agent/<id>/ on agent-notes, from a template."""

from collections.abc import Mapping
from pathlib import Path

from foundry import session
from foundry.errors import FoundryError
from foundry.github import GitHub

AGENT_NOTES_BRANCH = "agent-notes"


def load_template(template_dir: Path) -> dict[str, str]:
    """Every file directly in ``template_dir``, by name: what a new task's .agent/<id>/ starts with."""
    try:
        return {path.name: path.read_text() for path in sorted(template_dir.iterdir()) if path.is_file()}
    except FileNotFoundError:
        raise FoundryError(f"{template_dir} is missing") from None


def create(github: GitHub, repo_slug: str, task_id: str, template: Mapping[str, str]) -> None:
    """Create task/<id> from the default branch and copy ``template`` into .agent/<id>/ on agent-notes.

    Refuses if the task exists. agent-notes is created for the first task, as an orphan branch: it
    shares no history with the code.
    """
    session.require_valid_task_id(task_id)
    task_branch = f"task/{task_id}"
    files = {f".agent/{task_id}/{name}": text for name, text in template.items()}
    has_agent_notes_branch = github.branch_head(repo_slug, AGENT_NOTES_BRANCH) is not None
    existing_paths = [
        path
        for path in files
        if has_agent_notes_branch and github.file_text(repo_slug, path, AGENT_NOTES_BRANCH) is not None
    ]
    if github.branch_head(repo_slug, task_branch) is not None or existing_paths:
        raise FoundryError(f"task {task_id} already exists on {repo_slug}")
    default_branch = github.default_branch(repo_slug)
    base_sha = github.branch_head(repo_slug, default_branch)
    if base_sha is None:  # a repository with no commits yet
        raise FoundryError(f"{repo_slug} has no commits on {default_branch} to branch {task_branch} from")

    commit_message = f"Add task {task_id}"
    if has_agent_notes_branch:
        github.commit_files(repo_slug, AGENT_NOTES_BRANCH, files, commit_message)
    else:
        github.create_orphan_branch(repo_slug, AGENT_NOTES_BRANCH, files, commit_message)
    github.create_branch(repo_slug, task_branch, base_sha)
