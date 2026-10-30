# Progress

## Done
- Merged origin/HEAD into the task branch (clean, no conflicts).
- `ProjectClone.move_dir`; `Status` and `Task(id, status)` with `as_open`/`as_closed`/`from_id` in `task.py`; new `project_tasks.py` (`ProjectTasks`: create, close, reopen, is_closed, read_turn).
- `foundry task close` / `reopen` in `commands/task.py`; `foundry run` refuses a closed task via `require_open` before any sandbox, and always uses `ProjectTasks.read_turn`; `session.py` asserts an open task.
- Tests moved to the factories and new paths; new tests for move_dir, close, reopen, refusals, unsigned, is_closed, run's closed refusal, CLI parsing.
- Docs: README (table, `agent-notes` row, signing sentence), GLOSSARY, ARCHITECTURE codemap, ADR 0012 + adr README.
- Draft PR: https://github.com/WillCodeFoundry/willcode-foundry/pull/34 (migration snippet in the body). CI green.
- pytest, ruff, ruff format, mypy pass.

Status: ready for review

## In progress

## Next
- Reviewer: note I kept the Task and ProjectTasks tests in `tests/test_task.py` (shared git fixtures) rather than splitting the file as DESIGN.md says.
- Follow-up (not done): this sandbox's own `AGENT_TASK_NOTES_DIR` is the old `.agent/wcf-0027`; new layout applies to sandboxes created after merge.

## Blockers
