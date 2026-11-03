# Names

| Name | Kind | Where | Why |
|---|---|---|---|
| `TaskSummary` | class | `src/foundry/project_tasks.py` | New word. A `Task` and its turn. Not `TaskTurn`, `TaskAssignment` (implies a standing owner) or `TaskStatus` (clashes with `Status`, open/closed). |
| `MissingPathError` | exception | `src/foundry/project_clone.py` | New word. A path that isn't the dir or file asked for on a fetched branch. Narrow on purpose: an unfetched branch raises plain `FoundryError`. |
| `fetch_branch`, `local_list_dir`, `local_read` | methods | `src/foundry/project_clone.py` | `local_` marks the no-network pair; `read` is the existing fetching call. |
| `list_open_task_summaries` | method | `src/foundry/project_tasks.py` | Follows `get_task_by_id`, `read_task_turn`. |
| `ProjectListing`, `listing_lines`, `list_projects` | class, functions | `src/foundry/commands/task.py` | Apart from `report`, which reports one changed task. |
