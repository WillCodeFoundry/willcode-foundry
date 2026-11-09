# Review: wcf-0033

## Round 1, plan (reviewing PLAN.md at cf6461d)

No "TASK.md changed by another role" or "PLAN.md changed by another role" finding. Reviewed against TASK.md at
cf2da31, signed by the planner's identity, which the architect shares, so a change by the architect can't be told
apart from one by the planner. TASK.md's other commits are 78791b2, by the same identity, and ad55555, the human's
`Add task wcf-0033`. PLAN.md's commits are f003842, b2cdf6c and cf6461d, all signed by the dev, after ad55555.
No earlier findings.

### Standards
- The plan cites DR1, DR6 and DR7 (`ARCHITECTURE.md:76`, `:81`, `:82`), and each citation says what the plan
  claims. No design trigger: the plan adds no module, breaks no rule or ADR, and keeps `ProjectTasks.create_task`
  word for word.
- **R1, Blocking: the help planned for TASK contradicts AC6 as D1 amends it.** PLAN.md's Docs give the help for
  TASK (`src/foundry/commands/task.py:25`) as "default: the next one after the highest the project has taken,
  with its prefix". That reads as the prefix of the highest id. AC6 follows the prefix that most taken ids use.
  A user with `wcf-0001`…`wcf-0032` and a stray `sbx-0050` who reads `--help` would expect `sbx-0051`, and gets
  `wcf-0033`. Anyone on a mixed-prefix project who reads `--help` hits this. Direction: word it like the plan's
  README sentence (the prefix most ids use, then one more than its highest number). Shares a cause with R8.
- **R2, Follow-up: two descriptions of `task.py` are left out of the Docs list.** They are the module docstring at
  `src/foundry/task.py:1` ("what a task's names are, and the task template") and the codemap row at
  `ARCHITECTURE.md:29`. Neither mentions `next_task_id`. They become incomplete, not untrue. An agent using the
  codemap to find where the next id is chosen would look in `project_tasks.py` first. Direction: add both to the
  Docs list.
- **R3, Follow-up: say which module docstring sentence changes.** `src/foundry/project_tasks.py:5-6` says "callers
  pass task ids. Listing is the exception: it reads every dir under OPEN_DIR from one fetch". `create_next_task`
  becomes a second exception: it takes no id, and it reads `OPEN_DIR` and `CLOSED_DIR` both. The Docs list
  already covers the module docstring. Direction: name this sentence in it, so the rewrite doesn't miss it.

### Spec
Every criterion AC1–AC11 has a test at a named seam, and the steps cover them all. No step does what OS1–OS6 rule
out. The helpers the plan names all exist and do what it assumes: `project_repository`, `edit_notes`, `head`,
`enter_foundry`, `write_foundry`, and `scripted_stand_in` (`tests/support/machine.py:34`).
- **R4, Follow-up: the AC7 test can't tell whose commit survived.** AC7: "holds only the first's task branch,
  notes dir and commit, with nothing from the second". Both creates pick the same id and write the same template,
  with the same subject and key, so "both the competitor's" is never checked. The count does show there was no
  retry. But the test would also pass if the second create's commit replaced the first's. That can't happen today,
  because `push_atomic` never forces. Direction: have the stand-in record the tip of `agent-notes` once the
  competitor finishes, and assert the final tip equals it.
- **R5, Follow-up: the AC1 test checks less than "the same as `foundry task create PROJECT wcf-0034` would
  leave".** It doesn't assert the notes commit's subject, `Add task wcf-0034` (`src/foundry/project_tasks.py:99`).
  The risk is low, since both paths share `_create`. Direction: assert the subject, or accept as is.
- **R6, Follow-up: the setup for the AC5/AC6 CLI test isn't named.** If the seeded `tst-0000` and `cls-0000` stay,
  they tie with `abc` and `wcf` at one id each, and the expected stderr is wrong. `project_repository` seeds
  `agent-notes`, and the plan doesn't say how the test reaches "no `agent-notes`". Direction: name the setup, as
  AC1's test does.

### Names
Clean: `next_task_id`, `NoNextTaskIdError`, `ProjectTasks.create_next_task`, `_create`, `_taken_task_ids`, the
regex groups `prefix` and `number`, and `create_task` in `commands/task.py`. TASK becoming optional is clean, and so
are the two error texts: "the project repository" and "Give TASK" match the existing messages. The README, GLOSSARY
and ARCHITECTURE prose is clean too.
- **R7, Blocking: `BRANCH_PREFIX` is a homonym of the task id's prefix** (PLAN.md Steps 1 and 3, Names). TASK.md's
  Terms make "prefix" the letters of a task id (`wcf`). The plan uses the word that way for the regex group and in
  `next_task_id`. `BRANCH_PREFIX = "task/"` gives the word a second meaning in the same module. Step 3 already
  slips on it: "each branch starting with `BRANCH_PREFIX`, prefix removed". The next reader of `_taken_task_ids`
  will find both meanings in one function. Direction: name the constant after GLOSSARY.md's **Task branch**,
  without "prefix".
- **R8, Blocking: the help planned for TASK reads the opposite of the code** (PLAN.md Docs, the `create` parser's
  TASK help). It predicts the prefix of the highest id, where D1 and AC6 pick the most common prefix. AC10's text
  is the one users read. Direction: as R1. Shares a cause with R1.

### Summary
Standards: 3 findings, 1 Blocking (R1, the TASK help contradicts AC6). Spec: 3 findings, none Blocking (worst: R4,
the AC7 test can't tell whose commit survived). Names: 2 findings, both Blocking (worst: R7, the `BRANCH_PREFIX`
homonym). No design questions.

Verdict: plan changes needed
