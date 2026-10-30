# Task notes are split into open and closed

A task's notes dir sits under `.agent/tasks/open/<id>/` while the task is in progress, and under `.agent/tasks/closed/<id>/` once it is finished. `foundry task close` and `foundry task reopen` move the dir between the two, in one signed commit on `agent-notes`. Listing `.agent/tasks/open/` then shows exactly the tasks in progress. This supersedes the notes layout in [ADR 0006](0006-a-task-is-two-branches.md), `.agent/<id>/`. The rest of that ADR stands. The notes root stays `.agent/`, so the hook that keeps notes off task branches covers both dirs unchanged. `foundry run` refuses a closed task.

## Considered options

- **A separate `.agent-archive/` root for closed tasks.** The hooks keep notes off task branches by the one root, so a second root would need a change to each of them.
- **A migrate command for existing tasks.** The move is a one-off, so the pull request carries a bash snippet instead, which the owner runs by hand after merging.
