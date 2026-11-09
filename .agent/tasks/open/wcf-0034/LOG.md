# Log

## 1 · planner · planned
Done: TASK.md drafted with the human and approved: `foundry task show PROJECT
TASK` prints a task's turn and its LOG.md's last entry (AC1–AC9, OS1–OS9).
It replaces wcf-0030, which the human closed. The human chose to reuse
foundry's existing messages for an unknown project, an invalid id and a task
not found or both open and closed. A malformed task (TURN or LOG.md missing,
not a file or a symlink, or an empty TURN) just fails with an error naming
the task and the file. No follow-ups are recorded on the code this touches.
Next: the dev writes PLAN.md.

## 2 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0034 (already up to date). Wrote PLAN.md:
`foundry task show` reads through a new `ProjectTasks.fetch_task_turn_and_log`
(one fetch), refuses links with a new `FetchedBranch.is_link`, and cuts the
entry with a pure `last_log_entry`. Step 1 moves the counting stand-in for git
into `tests/support/` so AC4 and AC6 reuse it.
Next: the reviewer's plan round; then step 1 of PLAN.md.

## 3 · reviewer · plan-changes
Done: plan round 1 on PLAN.md at 24ff9dd, in REVIEW.md. TASK.md e475e61 (planner's identity, shared with the architect) and PLAN.md 24ff9dd (dev) are signed by allowed identities. No design trigger. Blocking: R1 (AC6 fetch count only at `ProjectTasks`, not end to end; nothing shows AC4's empty call log could see git), R2 (AC8's README sentence has no test or reason), R6 (`counting_git` outside the `*_stand_in` family, two return shapes), R7 (`fetch_count(log)`: "log" is the glossary's LOG.md). Follow-ups: R3, R4, R5.
Next: the dev revises PLAN.md for R1, R2, R6, R7 (and R3–R5 if cheap), answers each in LOG.md, and hands back with plan-ready.
- Follow-up: src/foundry/project_scratch_clone.py:49 `FetchedBranch.read_text` · returns a link's target name as if it were the file's text · every caller must remember to check `is_link` first.
- Follow-up: tests/support/machine.py:77 `recording_stand_in` · its record is named `log` · clashes with the glossary's Log in every test using it.
- Follow-up: src/foundry/project_tasks.py:127 `fetch_task_turn` · returns a `str` beside the `TaskTurn` dataclass · a reader at the call site expects a `TaskTurn`.
