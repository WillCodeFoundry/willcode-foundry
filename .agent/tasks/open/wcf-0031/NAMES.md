# Names

| Name | Kind | Where | Why |
|---|---|---|---|
| `hand_on_turn` | method | `src/foundry/project_tasks.py` | New word, from the README's "To hand it on yourself". Searched: hand_off, handoff, set_turn, move_turn; none in the code. Not `turn_task`: `turn` is a noun here. |
| `TurnChange` | class | `src/foundry/project_tasks.py` | New word: a task's turn before and after a hand-off. Searched: hand-off, transition; none in the code. |
| `before`, `after` | attributes | `TurnChange` | Not `old`/`new`: TASK.md's `<old>`/`<new>` are placeholders, and `before`/`after` read as times at `change.before`. |
| `log_with_turn_entry` | function | `src/foundry/project_tasks.py` | New word. A noun phrase, as it returns the log's new text and writes nothing. |
| `require_turn_arguments` | function | `src/foundry/commands/task.py` | Follows `require_open_task_and_role` in `run.py`: returns a value or refuses. Not `check_`, which returns a report (`repo_policy.check_project`). |
| `turn_report` | function | `src/foundry/commands/task.py` | Sibling of `report`, for an action that has no `Outcome`. |
| `foundry task turn` | interface name | `src/foundry/commands/task.py` | Given by TASK.md. |
| `hand_on_open_task_turn` | function | `src/foundry/commands/task.py` | Wraps `ProjectTasks.hand_on_turn` with the open-task check, as `require_open_task_and_role` does in `run.py`; "open" says what it adds. Its local `found` is a `Task`, not `task`, which names the `foundry.task` module there; `create_task` uses `found` too. |
