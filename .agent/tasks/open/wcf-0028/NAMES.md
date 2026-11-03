# Names

| Name | Kind | Where | Why |
|---|---|---|---|
| `TaskSummary` | class | `src/foundry/project_tasks.py` | New word. A `Task` and its turn. Not `TaskTurn`, `TaskAssignment` (implies a standing owner) or `TaskStatus` (clashes with `Status`, open/closed). |
| `MissingPathError` | exception | `src/foundry/project_clone.py` | New word. A path that isn't the dir or file asked for on a fetched branch. Narrow on purpose: an unfetched branch raises plain `FoundryError`. |
| `fetch_branch`, `local_list_dir`, `local_read` | methods | `src/foundry/project_clone.py` | `local_` marks the no-network pair; `read` is the existing fetching call. |
| `list_open_task_summaries` | method | `src/foundry/project_tasks.py` | Follows `get_task_by_id`, `read_task_turn`. |
| `ProjectListing`, `listing_lines`, `list_projects` | class, functions | `src/foundry/commands/task.py` | Apart from `report`, which reports one changed task. |
| `read_project_listing` | function | `src/foundry/commands/task.py` | Not `list_project`: one letter from `list_projects`, which only chooses projects. `read` because it clones and fetches, and returns a `ProjectListing`. |
| `_read_local_task_summary` | method | `src/foundry/project_tasks.py` | A verb, since it reads git; `local` as in `local_read`, no network. |
| `_open_task_in_dir` | function | `src/foundry/project_tasks.py` | New word. Pure, like `Task.as_open`, so a noun phrase as `_turn_of` is. Searched: `task_from_dir`, `parse_task`; none in use. |
| ~~`_open_task_in_dir`~~ | removed | `src/foundry/project_tasks.py` | Removed in 17606fe, at the human's request: one caller, and only wrapped `Task`'s error. The ids are built in a comprehension under one `try` in `list_open_task_summaries`. |
