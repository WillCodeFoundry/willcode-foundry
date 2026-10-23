"""Tasks on a project's GitHub repository: a task/<id> branch, and .agent/<id>/TASK.md on agent-notes.

agent-notes holds every task's notes, so it must exist before any task does.
"""

from dataclasses import dataclass

from foundry import session
from foundry.errors import FoundryError
from foundry.github import GitHub

NOTES_BRANCH = "agent-notes"
_NOTES_BRANCH_FILES = {".agent/README.md": "Task notes, one folder per task: .agent/<task>/.\n"}


@dataclass(frozen=True)
class CreatedTask:
    branch: str
    base_branch: str
    task_md_path: str


def has_notes_branch(github: GitHub, repo_slug: str) -> bool:
    return github.branch_head(repo_slug, NOTES_BRANCH) is not None


def ensure_notes_branch(github: GitHub, repo_slug: str) -> bool:
    """Create agent-notes, sharing no history with the code, unless it exists; return whether it was created."""
    if has_notes_branch(github, repo_slug):
        return False
    github.create_orphan_branch(repo_slug, NOTES_BRANCH, _NOTES_BRANCH_FILES, f"Start {NOTES_BRANCH}")
    return True


def create(github: GitHub, repo_slug: str, task_id: str, task_md: str) -> CreatedTask:
    """Create task/<id> from the default branch and commit TASK.md to agent-notes; refuse if the task exists."""
    session.require_valid_task_id(task_id)
    branch, task_md_path = f"task/{task_id}", f".agent/{task_id}/TASK.md"
    if not has_notes_branch(github, repo_slug):
        raise FoundryError(f"{repo_slug} has no {NOTES_BRANCH} branch; `foundry repo check --fix` creates it")
    existing_task_md = github.file_text(repo_slug, task_md_path, NOTES_BRANCH)
    if github.branch_head(repo_slug, branch) is not None or existing_task_md is not None:
        raise FoundryError(f"task {task_id} already exists on {repo_slug}")
    base_branch = github.default_branch(repo_slug)
    base_sha = github.branch_head(repo_slug, base_branch)
    if base_sha is None:  # a repository with no commits yet
        raise FoundryError(f"{repo_slug} has no commits on {base_branch} to branch {branch} from")

    github.create_file(repo_slug, NOTES_BRANCH, task_md_path, task_md, f"Add task {task_id}")
    github.create_branch(repo_slug, branch, base_sha)
    return CreatedTask(branch, base_branch, task_md_path)
