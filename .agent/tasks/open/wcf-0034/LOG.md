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
