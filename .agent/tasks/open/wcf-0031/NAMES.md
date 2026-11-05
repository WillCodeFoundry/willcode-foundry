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
| `tests/support/project_repository.py` | test module | `tests/support/` | Named for the class it holds, as CONTRIBUTING.md puts shared helpers in `tests/support/`. |
| `git_output` | function | `tests/support/project_repository.py` | git's stripped output, run in an env. Not `git`: `tests/support`'s `git(cwd, …)` returns a CompletedProcess. |
| `make_git_env`, `ProjectRepository.seed` | function, classmethod | `tests/support/project_repository.py` | What the conftest fixtures `git_env` and `project_repository` build from. |
| `foundry task handoff` (was `task turn`), `handoff_main` (was `turn_main`) | command, function | `src/foundry/commands/task.py` | Rename, at the human's call: the command is the act, a verb like `create`, `close` and `reopen`; GLOSSARY's "Handoff". TASK.md amended. |
| `human · handoff` (was `human · turn`), `Handoff of task …` (was `Turn of task …`), stdout `handoff <old> → <new>` | log heading, commit message, output | `src/foundry/project_tasks.py`, `src/foundry/commands/task.py` | An entry's third word names what happened, as outcomes do. The `Turn: <old> → <new>.` line keeps "turn": it shows the state moving. |
| `log_with_handoff_entry` (was `log_with_turn_entry`), `HANDOFF_CONFIG` (was `TURN_CONFIG`) | function, test constant | `src/foundry/project_tasks.py`, `tests/test_task_command.py` | The entry records a handoff; `TURN_CONFIG` read like a spelling of `TURN_FILE`. |
| `MissingTurnFileError` (was `NoTurnError`) | exception | `src/foundry/project_tasks.py` | Rename, at the human's call: names what is wrong in the notes, the TURN file. Also raised for a TURN that is a dir or holds only blanks, as its docstring says. |
| `MissingTurnError` (was `MissingTurnFileError`) | exception | `src/foundry/project_tasks.py` | Rename, at the human's call: TURN missing, a dir or blank all mean the task has no turn, as the message says. Replaces the row above. |
| `test_bad_handoff_args_are_refused_naming_the_problem` (was `…_refused_before_any_git`), `test_handoff_prints_where_the_task_went_or_an_error_and_exits_accordingly` (was `…_prints_the_turns_…`), `test_listing_fails_on_a_task_without_a_turn` (was `test_a_missing_empty_or_directory_turn_fails_naming_the_task`) | tests | `tests/test_task_command.py`, `tests/test_project_tasks.py` | Each names what it can fail on: the old names claimed "before any git", which a function without a repository can't show, and "the turns", which stdout no longer prints. |
| `ProjectRepository.notes_head` (from `head()`'s default), `head(branch)` | methods | `tests/support/project_repository.py` | R20: `head()` read as main's tip but returned agent-notes'. `notes_head` is named as its siblings `notes_files`, `notes_tree`, `notes_commits` are; `head` now requires the branch. Every no-argument call moved to `notes_head`. |
| `stand_in_dir`, `git_ran` | locals | `tests/test_task_command.py` | R17: the folder of the stand-in git on PATH, and the mark it leaves when run. |
| `path_with_stand_in` | function | `tests/support/__init__.py` | R24: returns a PATH value, with the stand-in's folder first, so the name leads with what it returns. "Stand-in" is the tests' word (`tests/support/machine.py`'s `stand_in`, CONTRIBUTING.md:42). Rejected: `stand_in_dir` (the dir alone leaves each caller joining PATH its own way, which R24 found). |
| `stand_in_path` (replaces `stand_in_dir`), `counting_path` | locals | `tests/test_task_command.py`, `tests/test_project_tasks.py` | The PATH values `path_with_stand_in` returns. |
