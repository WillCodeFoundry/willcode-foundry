# Progress

## Done
- Merged origin/HEAD into the task branch (clean, no conflicts).
- `ProjectClone.move_dir`; `Status` and `Task(id, status)` with `as_open`/`as_closed`/`from_id` in `task.py`; new `project_tasks.py` (`ProjectTasks`: create, close, reopen, is_closed, read_turn).
- `foundry task close` / `reopen` in `commands/task.py`; `foundry run` refuses a closed task via `require_open` before any sandbox, and always uses `ProjectTasks.read_turn`; `session.py` asserts an open task.
- Tests moved to the factories and new paths; new tests for move_dir, close, reopen, refusals, unsigned, is_closed, run's closed refusal, CLI parsing.
- Docs: README (table, `agent-notes` row, signing sentence), GLOSSARY, ARCHITECTURE codemap, ADR 0012 + adr README.
- Draft PR: https://github.com/WillCodeFoundry/willcode-foundry/pull/34 (migration snippet in the body). CI green.
- pytest, ruff, ruff format, mypy pass.

- Round 2 approved. Merged origin/HEAD (already up to date), CI green, PR body and title written with the `pr` skill (via `gh api`; `gh pr edit` fails on missing `read:org` scope), PR marked ready. No commits after the approval.

- PR description rewritten (2026-10-30 15:22 UTC) for the updated `pr` skill: Task section is one line plus a "For you to do" exception, Summary as diffs, Evidence names the failing test. Title unchanged. No code commits since round 2.

- Fresh review round 1 (changes needed) and the architect's DESIGN.md answers (85a2016) arrived. Merged origin/HEAD (12da10e, clean); checks pass. PR #34 back to draft.

## In progress
- Answering review round 1 against the new DESIGN.md.

## Next
1. R4: `ProjectClone.move_dir` stages the move with `git mv` (keeps every blob and mode under global excludes and `core.autocrlf`); test it.
2. R1, R13, R11: `task.py`: `Status` a plain enum mapped to dirs, no `isinstance`, `from_id_and_status`.
3. R1, R3, R12: `project_tasks.py`: id-in API (`get_task_by_id`, `create_task`, `close_task`, `reopen_task`, `read_task_turn`), `TaskNotFoundError`, `in_scratch_clone`; `create_task` checks the dirs before the branch; no asserts.
4. R6, R9: `commands/task.py`: shared arguments, `in_scratch_clone`, shared close/reopen body.
5. R7, R8: `commands/run.py`: one role-picking function, tested against a real repo with and without ROLE; refuse missing tasks too. `session.py` drops its assert.
6. R10: tidy the test helpers.
7. R2: ARCHITECTURE.md launch line and codemap; GLOSSARY "Status" sentence.
8. R5: fix the PR's Blast Radius.
9. Answer each finding in REVIEW.md, CI green, turn to reviewer.

## Blockers
