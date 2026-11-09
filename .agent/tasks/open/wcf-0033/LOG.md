# Log

## 1 · planner · planned
Done: TASK.md drafted with the human in one grilling round and approved: `foundry task create PROJECT`
without TASK picks the project's next task id (AC1–AC11, OS1–OS6). No follow-ups touch the code.
Next: the dev writes PLAN.md.

## 2 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0033 (already up to date). Wrote PLAN.md: a pure `next_task_id` in
`task.py`, `ProjectTasks.create_next_task` sharing `create_task`'s reads and push, and an optional TASK in
`foundry task create`, with a test named for each of AC1–AC11. No code yet.
Next: on plan approval, step 1 of PLAN.md, the refactor in `task.py`.

## 3 · dev · task-question
Done: the human, in this session, changed how the prefix is chosen. PLAN.md is amended to it (step 2, Errors,
Tests, Docs); it still needs its plan round once TASK.md holds the change. Entry 2's plan-ready is superseded.
- Asks D1 → planner: AC6 refuses whenever the taken ids use more than one prefix. Should create instead follow
  the most common prefix?
- Answers D1: yes. The prefix is the one the most taken ids use, counting each open, closed or branch-only id
  once. The number is one more than the highest among that prefix's ids only: `wcf-0001…wcf-0032` with
  `sbx-0050` give `wcf-0033`. Create refuses only when two or more prefixes tie for the most ids, naming the tied
  prefixes in alphabetical order and saying to give TASK; AC6's example, `abc-0001` and `wcf-0002`, still
  refuses. (the human)
Next: the planner folds D1 into TASK.md (AC6, the Goal); then the dev ends with plan-ready for the plan round.

## 4 · planner · planned
Done: folded the human's answer to D1 into TASK.md in cf2da31: the Goal and AC6 now follow the prefix most taken
ids use, numbering from that prefix's ids only, and refuse only on a tie. Both lines end `Amended: D1`.
- Answers D1: TASK.md amended in cf2da31 (Goal, AC6); no other criterion changed.
Next: the dev checks PLAN.md against the amended AC6 and ends with plan-ready for the plan round.

## 5 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0033 (already up to date). Checked PLAN.md against TASK.md as cf2da31
amends it: step 2, Errors and Tests already follow D1 (most common prefix, its own highest number, refusal on a tie
naming the tied prefixes sorted). Added a test for AC6's "counting each id once": open `wcf-0001`/`wcf-0002` with
their branches beside branch-only `sbx-0050…0052` give `sbx-0053`. No code yet.
Next: on plan approval, step 1 of PLAN.md, the refactor in `task.py`.

## 6 · reviewer · plan-changes
Done: plan round 1 on PLAN.md at cf6461d, against TASK.md at cf2da31. The history of both files is clean. Three
findings block: R1 and R8 (one cause), where TASK's planned `--help` text says the highest id's prefix but AC6 picks
the most common one; and R7, where `BRANCH_PREFIX` is a homonym of the task id's prefix. The follow-ups R2–R6 are in
REVIEW.md, round 1. No design questions.
Next: the dev revises PLAN.md for R1, R7 and R8 (and any follow-ups it takes) and ends with plan-ready.
- Follow-up: src/foundry/task.py:83 · the docstrings at :83, :88, :93 and :98 say "relative to the repository root",
  which GLOSSARY.md's Avoid list replaces with "working tree" · readers meet two words for one place.

## 7 · reviewer · plan-changes
Done: the human changed the direction of R7 in this session. The outcome and the other findings are unchanged.
- Answers R7: `BRANCH_PREFIX` may stay, as long as the task id's own part is never called `prefix` alone. Its names
  must say whose prefix it is: `TASK_PREFIX`, or something else that says so, for the regex group, for
  `next_task_id`'s locals and for the error text. R7 stays Blocking, but it now applies to those names, not to
  `BRANCH_PREFIX`. Also write the rule into GLOSSARY.md's **Task id** entry, which the plan already sharpens, with
  bare "prefix" under _Avoid_. (the human)
Next: the dev revises PLAN.md for R1, R7 as answered here, and R8, then ends with plan-ready.

## 8 · reviewer · plan-changes
Done: the human confirmed, in this session, the behaviour behind R1 and R8. The findings stand, with a sharper
direction.
- Answers R1, R8: only the task ids with the most popular prefix count. Ids with any other prefix are ignored
  completely, so `wcf-0001`…`wcf-0032` with `sbx-0050` correctly give `wcf-0033`. This is what AC6 already says,
  and the plan's code is right. Only its `--help` text for TASK is wrong, because it reads as "the prefix of the
  highest id". Word the help, and the README sentence too, so that they say the most popular prefix is followed
  and ids with other prefixes are ignored. (the human)
Next: the dev revises PLAN.md for R1/R8 as answered here and for R7 as answered in entry 7, then ends with
plan-ready.
