# Progress

## Done
- Merged origin/HEAD into the task branch (clean, no conflicts); host tier green before changes.

## In progress
- Starting on DESIGN.md, step 1.

## Next
1. `ProjectClone.move_dir` (test-first).
2. `task.py`: `Status`, `Task(id, status)`, factories, open/closed paths; `tests/test_task.py` Task properties.
3. `project_tasks.py`: `ProjectTasks` with create, close, reopen, is_closed, read_turn; tests against a real bare repo.
4. `commands/task.py` close/reopen; `commands/run.py` closed refusal and `read_turn`; `session.py` open assertion.
5. Move remaining tests (`test_run`, `test_session`, `test_task_contract`, conftest, support) to the factories.
6. Docs: README, GLOSSARY, ARCHITECTURE codemap, ADR 0012 + adr README.
7. Checks (pytest, ruff, mypy), draft PR with the one-off move snippet in its description, CI, hand to reviewer.

## Blockers
