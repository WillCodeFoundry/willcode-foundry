"""Tasks on a project's GitHub repository: a task/<id> branch and its .agent/<id>/TASK.md on agent-notes."""

from dataclasses import dataclass

from foundry import session
from foundry.errors import FoundryError
from foundry.github import GitHub

NOTES_BRANCH = "agent-notes"
NOTES_README = {
    ".agent/README.md": "Task notes, one folder per task: .agent/<task>/TASK.md, PROGRESS.md, LEARNINGS.md.\n"
}
"""What a new agent-notes branch starts with: it shares no history with the code."""


@dataclass(frozen=True)
class CreatedTask:
    task_branch: str
    base_branch: str
    task_md_path: str


def create(github: GitHub, repo_slug: str, task_id: str, task_md: str) -> CreatedTask:
    """Create task/<id> from the default branch and commit TASK.md to agent-notes; refuse if the task exists."""
    session.require_valid_task_id(task_id)
    task_branch, task_md_path = f"task/{task_id}", f".agent/{task_id}/TASK.md"
    if github.branch_head(repo_slug, NOTES_BRANCH) is None:
        raise FoundryError(f"{repo_slug} has no {NOTES_BRANCH} branch; `foundry repo check --fix` creates it")
    existing_md = github.file_text(repo_slug, task_md_path, NOTES_BRANCH)
    if github.branch_head(repo_slug, task_branch) is not None or existing_md is not None:
        raise FoundryError(f"task {task_id} already exists on {repo_slug}")
    base_branch = github.default_branch(repo_slug)
    base_sha = github.branch_head(repo_slug, base_branch)
    if base_sha is None:
        raise FoundryError(f"{repo_slug} has no commits on {base_branch} to branch {task_branch} from")

    github.create_file(repo_slug, NOTES_BRANCH, task_md_path, task_md, f"Add task {task_id}")
    github.create_branch(repo_slug, task_branch, base_sha)
    return CreatedTask(task_branch, base_branch, task_md_path)
