# Names

| Name | Kind | Where | Why |
|---|---|---|---|
| `hand_on_turn` | method | `src/foundry/project_tasks.py` | New word, from the README's "To hand it on yourself". Searched: hand_off, handoff, set_turn, move_turn; none in the code. Not `turn_task`: `turn` is a noun here. |
| `TurnChange` | class | `src/foundry/project_tasks.py` | New word: a task's turn before and after a hand-off. Searched: hand-off, transition; none in the code. |
| `before`, `after` | attributes | `TurnChange` | Not `old`/`new`: TASK.md's `<old>`/`<new>` are placeholders, and `before`/`after` read as times at `change.before`. |
| `log_with_turn_entry` | function | `src/foundry/project_tasks.py` | New word. A noun phrase, as it returns the log's new text and writes nothing. |
| `require_project_and_turn_arguments` | function | `src/foundry/commands/task.py` | Renamed from `require_turn_arguments` (R13), so the name gives the result as well as the check, as `require_open_task_and_role` in `run.py` does. Not `check_`, which returns a report (`repo_policy.check_project`). |
| `turn_report` | function | `src/foundry/commands/task.py` | Sibling of `report`, for an action that has no `Outcome`. |
| `foundry task turn` | interface name | `src/foundry/commands/task.py` | Given by TASK.md. |
| `hand_on_open_task_turn` | function | `src/foundry/commands/task.py` | Wraps `ProjectTasks.hand_on_turn` with the open-task check, as `require_open_task_and_role` does in `run.py`; "open" says what it adds. Its local `found` is a `Task`, not `task`, which names the `foundry.task` module there; `create_task` uses `found` too. |
| `turn` | parameter, parser dest | `src/foundry/commands/task.py` | Renamed from `role_name` (R11): the value may be `human`, which GLOSSARY.md's "Turn" covers and "Role" doesn't. Matches `hand_on_turn`'s `turn`. The metavar stays `ROLE`, as TASK.md fixes it. |
| `turn_change` | local, parameter | `commands/task.py`, `tests/test_task.py` | Renamed from `change` (R10): named for `TurnChange`, and no longer a letter from `report`'s `changed`. `commands/repo.py`'s `change` (a `RulesetChange`) is older, and left as a follow-up. |
| `_read_fetched_turn_or_empty` | method | `src/foundry/project_tasks.py` | Renamed from `_read_fetched_turn_text` (R12): named for what sets it apart from `_read_fetched_turn`, the empty result for a missing or blank TURN_FILE. |
| `_read_fetched_log` | method | `src/foundry/project_tasks.py` | New (R6). Follows `_read_fetched_turn`; it refuses a missing LOG_FILE. |
| `_commit_and_push` | method | `src/foundry/project_tasks.py` | New (R5). Says both steps; NOTES_BRANCH is the only branch `ProjectTasks` pushes alone. |
| `ProjectTasks.handoff` | method | `src/foundry/project_tasks.py` | Renamed from `hand_on_turn`, the human's choice (LOG.md, entry 11): "handoff" is the word for a turn passing on, as ADR 0011's "hand-off". Replaces `hand_on_open_task_turn` too, which goes. Rejected: `pass_turn`, `set_turn` (hides the log entry). |
| `handoff_lines` | function | `src/foundry/commands/task.py` | Renamed from `turn_report`, which the human found unclear. `_lines` as `listing_lines`: what a command prints. |
| `require_valid_handoff_args` | function | `src/foundry/commands/task.py` | Replaces `require_project_and_turn_arguments`, the human's choice. Returns nothing, as `_require_on_branch`; the project is looked up in `turn_main`. |
| `handoff` (test helper) | function | `tests/test_task.py` | Renamed from `hand_on`, after the method it calls. |
| `NoTurnError` | class | `src/foundry/project_tasks.py` | New, beside `TaskNotFoundError`: a missing or blank TURN_FILE. `handoff` catches it; `_read_fetched_turn_or_empty` and the `fix` parameter go. |
| Handoff | glossary term | `GLOSSARY.md` | New. Clash: `agent_runtime/session_init.py` says "handoff to root" for root mode; flagged in GLOSSARY, not renamed. |

`TurnChange` and its `turn_change` locals are removed: `handoff` returns the turn before.
| `project_repository`, `ProjectRepository` | fixture, class | `tests/conftest.py` | The human's choice (LOG.md, entry 13). Stands in for "the GitHub repository behind a project", which GLOSSARY's "Project" allows calling a repository; pairs with `ProjectClone`. Rejected: `origin` (taken by a conftest fixture, and unclear), `remote_repository`, `project_repo` (GLOSSARY avoids "repo"). |
| `no_signing_key` | fixture | `tests/test_project_tasks.py` | Says the state the test runs in; only that module uses it. |
| `test_project_clone.py`, `test_project_tasks.py`, `test_task_command.py` | test modules | `tests/` | Named for the module each tests, as `test_task.py` is for `task.py`. |
