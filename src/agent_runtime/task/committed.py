"""A task state as committed: STATE.json read from a revision of the notes checkout.

The runtime's ``task`` command and its pre-push guard both read it this way. foundry reads it through ProjectClone.
Runs only in the sandbox: foundry never imports it.
"""

from agent_runtime.git import Git
from agent_runtime.task.state import TaskState


def committed_state(git: Git, revision: str, path: str) -> TaskState | None:
    """The task state at ``revision``:``path``; None when there is no file there, TaskStateRefused if it isn't one."""
    where = f"{revision}:{path}"
    if not git.succeeds("cat-file", "-e", where):
        return None
    return TaskState.parse(git.output("show", where), where)
