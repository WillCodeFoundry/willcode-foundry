# Names

| Name | Kind | Where | Why |
|---|---|---|---|
| `hand_on_turn` | method | `src/foundry/project_tasks.py` | New word, from the README's "To hand it on yourself". Searched: hand_off, handoff, set_turn, move_turn; none in the code. Not `turn_task`: `turn` is a noun here. |
| `TurnChange` | class | `src/foundry/project_tasks.py` | New word: a task's turn before and after a hand-off. Searched: hand-off, transition; none in the code. |
| `before`, `after` | attributes | `TurnChange` | Not `old`/`new`: TASK.md's `<old>`/`<new>` are placeholders, and `before`/`after` read as times at `change.before`. |
| `log_with_turn_entry` | function | `src/foundry/project_tasks.py` | New word. A noun phrase, as it returns the log's new text and writes nothing. |
| `read` | method | `src/foundry/project_clone.py` | Pairs with `write` on the checked-out files; `fetched_read` already names reading a fetched branch. |
