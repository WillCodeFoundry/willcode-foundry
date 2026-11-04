# Design: wcf-0031

## Decisions
- `foundry task turn` is for a task whose role isn't running, and the README
  says so; nothing checks it. Answers R3. A running role writes `TURN` when its
  turn ends, which would overwrite the hand-off. Its unpushed `LOG.md` entry
  would also conflict with the `human · turn` entry on its next
  `pull --rebase`. This rules out refusing while a sandbox runs (machinery in
  `commands/task.py` outside TASK.md), a `merge=union` attribute for `LOG.md`
  (hides the conflict and leaves two entries with one number), and changing
  `agent-kit/AGENTS.md`'s "never conflicts" rule: handing on a running task is
  a mistake the human avoids, as ADR 0011 leaves a mistyped `TURN` to them.

## Modules and seams
- `README.md`, the paragraph on `TURN`: one sentence saying to hand on a task
  only when its role isn't running (stop the session or let it finish its
  turn), because the role writes `TURN` when its turn ends and its log entries
  would conflict with yours.
- Names: none added.

## Design rules and ADRs
- ADR 0011: nothing checks a hand-off; the README advice adds no check.
- ADR 0013: the log stays append-only; foundry appends only when no role is
  writing it.
- Design rule 6: no handling of a failure the design avoids by instruction.

## Leave alone
- `agent-kit/AGENTS.md`'s "Notes checkout" section.
- `commands/task.py` and `project_tasks.py`: no check for a running sandbox.
