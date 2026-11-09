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
