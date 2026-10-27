---
name: address-review
description: "Answer a review round. Use when the latest round in the task's REVIEW.md says 'Verdict: changes needed', to fix or dispute each open finding before handing the task back to the reviewer."
---

# Address a review

The reviewer writes rounds in `$AGENT_NOTES_DIR/$AGENT_TASK_NOTES_DIR/REVIEW.md`,
each finding with an id (`R1`, `R2`, …). This is how you answer the latest one.

1. **Read the latest round,** and the hand-off note `"$AGENT_KIT_DIR/bin/task" show`
   prints. The open findings are the round's new ones and those it lists as
   still open. Findings it accepted as is need nothing.
2. **Decide each finding, by its id.** Fix it if it's right. Disagree if it's
   wrong, or if fixing it would go beyond `TASK.md`: the review checks the task,
   it doesn't widen it. If a finding contradicts `TASK.md` itself, don't pick a
   side: block the task with the question (see "When to stop and ask" in
   `AGENTS.md`).
3. **Fix test-first,** with the `tdd` skill: a test that shows the problem,
   then the fix. One commit per finding where you can, its id in the message
   (`fix(parser): R4 …`), so the reviewer can check each one.
4. **Answer under each finding,** never editing the reviewer's text:
   `Fixed in <commit>.` or `Disagree: <why>.` A disagreement gives a reason the
   reviewer can check: a line of `TASK.md`, a test, a measurement.
5. **Push the code, then the notes,** as `AGENTS.md`'s "Git rules" say. Then
   end your turn with a hand-off note saying what you fixed, what you disputed,
   and where to look first.

Never mark a finding closed yourself: the reviewer closes it in the next round.
