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
- Fresh review round 1 answered against DESIGN.md (85a2016) in `50180d1`: every finding, R1–R13, says how in REVIEW.md. R5 fixed in the PR description only. CI green on `50180d1`.
  - API now takes ids: `ProjectTasks.get_task_by_id`, `create_task`, `close_task`, `reopen_task`, `read_task_turn`, `in_scratch_clone`; `TaskNotFoundError`. `run.role_to_launch` replaces `require_open` and the role logic in `main`.
  - Beyond TASK.md, by DESIGN.md: `foundry run` refuses a missing task too.
- No merge conflicts this turn (12da10e merged clean).
- PR #34 is a draft again: it had been marked ready after the old round-2 approval.

Status: ready for review

## In progress

## Next
- Reviewer: round 2, against DESIGN.md at 85a2016. Branch head `50180d1`.
- Kept from before: Task and ProjectTasks tests share `tests/test_task.py` (shared git fixtures), not split as an earlier DESIGN.md said.
- This sandbox's own `AGENT_TASK_NOTES_DIR` is the old `.agent/wcf-0027`; the new layout applies to sandboxes created after merge.

## Blockers
