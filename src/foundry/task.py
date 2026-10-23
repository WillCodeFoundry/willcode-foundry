"""Tasks on a project's GitHub repository: a task/<id> branch, and .agent/<id>/TASK.md on agent-notes."""

from foundry import session
from foundry.errors import FoundryError
from foundry.github import GitHub

AGENT_NOTES_BRANCH = "agent-notes"


def create(github: GitHub, repo_slug: str, task_id: str, task_md: str) -> None:
    """Create task/<id> from the default branch and commit TASK.md to agent-notes; refuse if the task exists.

    agent-notes is created for the first task, as an orphan branch: it shares no history with the code.
    """
    session.require_valid_task_id(task_id)
    task_branch, task_md_path = f"task/{task_id}", f".agent/{task_id}/TASK.md"
    has_agent_notes_branch = github.branch_head(repo_slug, AGENT_NOTES_BRANCH) is not None
    existing_task_md = github.file_text(repo_slug, task_md_path, AGENT_NOTES_BRANCH) if has_agent_notes_branch else None
    if github.branch_head(repo_slug, task_branch) is not None or existing_task_md is not None:
        raise FoundryError(f"task {task_id} already exists on {repo_slug}")
    default_branch = github.default_branch(repo_slug)
    base_sha = github.branch_head(repo_slug, default_branch)
    if base_sha is None:  # a repository with no commits yet
        raise FoundryError(f"{repo_slug} has no commits on {default_branch} to branch {task_branch} from")

    commit_message = f"Add task {task_id}"
    if has_agent_notes_branch:
        github.create_file(repo_slug, AGENT_NOTES_BRANCH, task_md_path, task_md, commit_message)
    else:
        github.create_orphan_branch(repo_slug, AGENT_NOTES_BRANCH, task_md_path, task_md, commit_message)
    github.create_branch(repo_slug, task_branch, base_sha)
