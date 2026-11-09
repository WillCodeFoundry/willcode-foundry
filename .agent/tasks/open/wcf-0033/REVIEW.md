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

## Round 2, plan (reviewing PLAN.md at 97f5e0c)

No "TASK.md changed by another role" or "PLAN.md changed by another role" finding. Reviewed against TASK.md at
cf2da31, signed by the planner's identity, which the architect shares, so a change by the architect can't be told
apart from one by the planner. TASK.md has no commit since round 1. PLAN.md's only new commit is 97f5e0c, signed by
the dev. This round reviews the fix diff `cf6461d..97f5e0c`, judged against the answers in LOG.md entries 7–9.

Earlier findings:
- R1: closed. The TASK help and the README sentence now say the next id follows the task prefix most ids use, and
  that ids with other prefixes are ignored, as entry 8 asks. Both are true of step 2.
- R2: closed. `task.py`'s module docstring and its codemap row (`ARCHITECTURE.md:29`) are now in the Docs list.
- R3: closed. The Docs list names the `src/foundry/project_tasks.py:5-6` sentence. Its new wording has a slip of its
  own, raised as R11.
- R4: closed. The stand-in records the tips of `agent-notes` and the task branch once the competitor finishes, and
  the test asserts the final tips equal them. `scripted_stand_in` (`tests/support/machine.py:34`) can run that.
- R5: closed. The AC1 method test asserts the subject `Add task wcf-0034`.
- R6: closed. Both setups work with the existing helpers. `edit_notes` takes `remove=`
  (`tests/support/project_repository.py:87`). The seed pushes only `main` and `agent-notes`
  (`tests/support/project_repository.py:149`), so deleting `agent-notes` leaves no id taken.
- R7: closed, as entry 7 answers it. The regex group, the locals and the error text say `task_prefix` or "task
  prefix". `BRANCH_PREFIX` stays. The _Avoid_ rule is in the Docs list. The prose that rule now governs is R9.
- R8: closed, as R1.

### Standards
- **R11, Follow-up: the planned `project_tasks.py` docstring says the branches come from a fetch.** PLAN.md:111-113
  has `create_next_task` reading "`OPEN_DIR` and `CLOSED_DIR` and the task branches from one fetch". The branches
  come from `git ls-remote --heads` (`src/foundry/project_scratch_clone.py:102-107`). Only `NOTES_BRANCH` is
  fetched (`src/foundry/project_tasks.py:86-87`). A dev reading the docstring to find where taken ids come from
  would look in the wrong place, rarely and briefly. Direction: say the dirs come from one fetch of `NOTES_BRANCH`,
  and the branches from the remote's branch list.
- **R12, Follow-up: the planned prose breaks the _Avoid_ rule the same plan adds.** It says "a prefix of lowercase
  ASCII letters" (PLAN.md:102) and "ids with other prefixes" (PLAN.md:103, :117). Anyone who copies the README
  wording later breaks the rule. Direction: as R9. Shares a cause with R9.

No other doc is made untrue and left out of the list. `README.md:29` and `CONTRIBUTING.md:103` give TASK, which
stays valid.

### Spec
Every criterion AC1–AC11 still has a test at a named seam. No step does what OS1–OS6 rule out.
- **R10, Follow-up: the AC7 test's setup isn't named** (PLAN.md:85-91). AC7: "When two creates without TASK pick
  the same id…". On the plain seeded repository, `tst-0000` and `cls-0000` tie, so both creates would refuse
  before any push and no race would happen. The "one new task branch" assertion would then fail, so the test
  can't pass by accident. The dev hits this once, while writing the test. Direction: name the setup as R6 does,
  with the seeded tasks removed or one task prefix holding the most ids.

### Names
Clean: the regex group `task_prefix`, `next_task_id`'s locals `task_prefix` and `task_prefixes`, "with
`BRANCH_PREFIX` cut off", the tie error's "most common task prefix", the ARCHITECTURE and docstring wording, and the
GLOSSARY term **task prefix**. `git grep -w prefix` finds no clashing use.
- **R9, Blocking: the new prose uses bare "prefix", the word the plan itself puts under _Avoid_.** PLAN.md:105-107
  adds "prefix (alone, for a task id's letters)" to the _Avoid_ list of GLOSSARY.md's **Task id**, as the human
  asked in entry 7. Three places still break it:
  - The README's task id line, "a prefix of lowercase ASCII letters" (PLAN.md:102), uses it.
  - The GLOSSARY entry is written "as TASK.md's Terms sharpens it" (PLAN.md:105). TASK.md says "made of a prefix of
    lowercase ASCII letters", so the definition would use the word its own _Avoid_ line bans.
  - "ids with other prefixes" (PLAN.md:103, :117) is milder, since "task prefix" comes just before it.

  These lines are where the term is defined. Every later Names review checks prose against _Avoid_, and it can't
  tell whether the definition's own breach is meant. AC9 asks only that the README line "names its prefix and
  number", and "task prefix" does that. Direction: say "task prefix" in the README id line and the GLOSSARY
  definition, and "other task prefixes" in the README sentence and the help. Shares a cause with R12.

### Summary
Standards: 2 findings, none Blocking (worst: R12, prose against the new _Avoid_ rule). Spec: 1 finding, not
Blocking (R10, the AC7 setup isn't named). Names: 1 finding, Blocking (R9, bare "prefix" in the definitions). R1–R8
are closed. No design questions.

Verdict: plan changes needed

## Round 3, plan (reviewing PLAN.md at 6694061)

No "TASK.md changed by another role" or "PLAN.md changed by another role" finding. Reviewed against TASK.md at
cf2da31, signed by the planner's identity, which the architect shares, so a change by the architect can't be told
apart from one by the planner. TASK.md has no commit since round 2. PLAN.md's only new commit is 6694061, signed by
the dev. This round reviews the fix diff `97f5e0c..6694061`, judged against the answers in LOG.md entry 11.

Earlier findings:
- R9: closed. The README task id line, the GLOSSARY **Task id** definition, the README sentence and the TASK help
  now say "task prefix" or "other task prefixes" (PLAN.md:103-110, :120-121). So the definition keeps the _Avoid_
  rule it adds.
- R10: closed. The AC7 setup is named (PLAN.md:91-93): the seeded dirs are removed and `wcf-0030` is opened with
  `edit_notes`, so both creates pick `wcf-0031` and reach the push. `edit_notes` takes `write=` and `remove=`
  (`tests/support/project_repository.py:87`).
- R11: closed. The planned docstring says the dirs come from one fetch of `NOTES_BRANCH`, and the task branches from
  the remote's branch list (PLAN.md:114-118). That is true of `src/foundry/project_tasks.py:86-87` and
  `src/foundry/project_scratch_clone.py:102-107`.
- R12: closed, as R9.

### Standards
No new findings. Each changed line gives its reason with `Amended: R<n>. Because: …`. No doc is made untrue and
left out of the Docs list. Bare "prefix" is still used at PLAN.md:48 and :94, but only in the plan's own prose,
which ships nowhere, so it isn't reported.

### Spec
No new findings. AC1–AC11 each still have a test at a named seam. The wording changes leave what each test checks
unchanged. AC9's "names its prefix and number" and AC10's "says what is picked" are still met by the planned
README line and help. No step does what OS1–OS6 rule out.

### Names
No new findings. These are clean: "most common task prefix" and "other task prefix's higher number" (the D1 test),
"Ids with other task prefixes are ignored" (the README and the help), "a task prefix of lowercase ASCII letters"
(the README and GLOSSARY), and the docstring's "one fetch of `NOTES_BRANCH`" and "the remote's branch list".

### Summary
Standards: 0 findings. Spec: 0 findings. Names: 0 findings. R9–R12 are closed and none blocks. No design questions.

Verdict: plan approved at 6694061

## Round 4 (reviewing df11854)

No "TASK.md changed by another role" or "PLAN.md changed by another role" finding. Reviewed against TASK.md at
cf2da31, signed by the planner's identity, which the architect shares, so a change by the architect can't be told
apart from one by the planner. PLAN.md is unchanged since it was approved at 6694061, signed by the dev. This is the
first code round, so it reviews the whole diff `9e047ab...df11854` (ac5b7e0, df11854).

Earlier findings: R1–R12 were closed in the plan rounds. None is open.

### Standards
- R16 (Follow-up): `src/foundry/commands/task.py:32-33`. The description of `create` still says only "Refuses a task
  that already exists, open or closed." Without TASK, create now also refuses when no task id is taken and when task
  prefixes tie. The other actions' descriptions list every refusal they make, such as `reopen` at :55-56. Nothing in
  it is untrue, and the error itself says to give TASK, so a reader is rarely misled. Direction: add one sentence
  naming both refusals.

Compliant: DR1 (`BRANCH_PREFIX` spells "task/" once in `src/`), DR6 (`NoNextTaskIdError` says only what went wrong,
and the command adds "Give TASK"), DR7 (`create_main` only builds and passes). No sentence the change made untrue in
the docstrings of `task.py`, `project_tasks.py` or `commands/task.py`, the codemap rows, or README. "Task prefix" is
in GLOSSARY.md.

### Spec
- R17 (Follow-up): AC7, "the second exits 1 with an `error:` line on stderr". When two creates run as one identity in
  the same second, they make byte-identical commits. The second push then has nothing to push, so it exits 0. The
  AC7 test (`tests/test_task_command.py:193`) dates the competitor's commit differently to avoid this case. Only a
  script running two creates at once from one foundry hits it. The repository still holds exactly the first's
  work, and two creates of one explicit id behave the same today (TASK.md Risks, OS5). The dev disclosed it in
  LOG.md entry 14 and LEARNINGS.md. Direction: accept as is.

Every criterion is met, each by its code and a test:
- AC1: `ProjectTasks._create` and `commands.task.create_task`.
  `test_the_next_task_is_created_as_create_task_would_create_it` checks the branch, the notes files, the commit
  subject, the parent and the signature. `test_create_without_a_task_creates_the_next_one` checks the output.
- AC2: `test_the_highest_taken_number_counts_whichever_kind_holds_it[open|closed|branch]`.
- AC3: `test_the_next_task_id_is_one_more_than_the_highest_padded_to_four_digits`.
- AC4: `test_names_that_aren_t_task_ids_are_ignored` and `test_task_branches_that_aren_t_task_ids_are_ignored`.
- AC5: shown in `test_task.py`, `test_project_tasks.py` and the CLI test `[no-task-id]`, which checks exit 1, the
  stderr and that `for-each-ref` is unchanged.
- AC6: shown by the majority, counted-once and tie tests, and the CLI test `[tie]`.
- AC7: the race test checks the winner's tips, one task branch and no second notes dir. The same-second case is R17.
- AC8: `_create` still refuses an invalid given id before git runs. The existing tests are unchanged and pass.
- AC9: the README row and the task id line. `tests/test_docs.py` passes.
- AC10: `test_create_s_task_is_optional_and_its_help_says_what_is_picked_without_it`.
- AC11: ruff check, ruff format and the four test files pass.

The names, errors, seams and approach match the approved PLAN.md. No scope creep.

### Behaviour
No findings. Each case below was reproduced in a throwaway clone with the `project_repository` fixture, and passes:
- no `agent-notes` branch but a branch `task/wcf-0010` gives `wcf-0011`, with the notes branch created as an orphan;
- an id in both the open and closed dirs is counted once;
- `wcf-0041` beside `task/wcf-00041` gives `wcf-0042`;
- a tie with different numbers refuses, naming "abc, wcf", and leaves the remote's refs unchanged;
- a nested branch `task/wcf-0009/x` is ignored.

These were read and hold:
- an empty TASK is refused as an invalid id; it isn't treated as "pick the next one";
- `given_task or …` can't mistake a `Task` for None;
- `next_task_id` raises before any checkout, write, commit or push.

The host tier, ruff and mypy pass at df11854.

### Smells
Functions the diff adds or changes:
- `src/foundry/commands/task.py`: `add_parser` and `create_main` are clean. `create_task` is new, clean.
- `src/foundry/project_tasks.py`: `ProjectTasks.create_task` is clean, and `_create` is clean (its None switch is
  what PLAN.md step 3 decides). `create_next_task` and `_taken_task_ids` are new, clean.
- `src/foundry/task.py`: `Task.branch` is clean. `NoNextTaskIdError` and `next_task_id` are new, clean.
- `tests/test_task.py`: all five new tests are clean.
- `tests/test_project_tasks.py`: `take_task_ids` is new (R14).
  `test_the_highest_taken_number_counts_whichever_kind_holds_it` is new (R15). The other five new tests are clean.
- `tests/test_task_command.py`:
  - `foundry_of_store` and `test_create_s_task_is_optional_…` are new, clean.
  - `test_create_without_a_task_creates_the_next_one` is new (R14).
  - `test_create_without_a_task_that_can_t_pick_one_…` is new (R13, R14).
  - `test_a_create_that_loses_the_race_…` is new (R14). Its PATH stand-in is allowed by 10.4's "Fine when" and by
    design rule 3.

Findings:
- R13 (Blocking), possible 10.6, a parametrized test that asks which case it is: `tests/test_task_command.py:163`.
  - What: the shared body checks `if "tie" in error` to choose its setup. So the expected message also decides how
    the repository is built.
  - Who hits it: the next dev who adds a refusal case, or rewords the tie message. A message without "tie" quietly
    runs the other setup.
  - Direction: give the setup its own parameter, or split the test in two.
- R14 (Blocking), possible Duplicated Code / 6.6, rebuilding a place the code already names:
  - What: `SEEDED_TASK_NOTES_DIRS` is spelled by hand twice, at `tests/test_task_command.py:123` and
    `tests/test_project_tasks.py:141`. Yet `ProjectRepository` already names the seeded tasks, as `open_task` and
    `closed_task` (`tests/support/project_repository.py:68-69`).
  - Who hits it: whoever changes a seeded task. They would have to edit three places. A missed one leaves the seed in
    place, and the create-without-TASK tests then fail with a prefix tie, far from the edit.
  - Direction: derive the dirs from the seeded tasks `ProjectRepository` already names.
- R15 (Follow-up), possible 10.6: `tests/test_project_tasks.py:175`. The test builds its keyword arguments from
  `kind` with `f"{kind}_ids"` and `taken.get`, so the reader works out each case's setup. Direction: put each
  case's `take_task_ids` arguments in the parametrize table.

### Names
No findings. Every name the diff adds matches the one the approved PLAN.md gives:
- in the code: `next_task_id`, `NoNextTaskIdError`, `create_next_task`, `_create`, `_taken_task_ids`,
  `BRANCH_PREFIX`, the `task_prefix` and `number` groups, the `commands.task.create_task` function, and
  `project_argument`;
- in the tests: the helpers `take_task_ids` and `foundry_of_store`, and every test function;
- in the docs: the GLOSSARY **Task id** with its _Avoid_ entry.

The prose always says "task prefix", never bare "prefix".

### Summary
- Standards: 1 finding, 0 blocking. The worst is R16, where create's description leaves out the new refusals.
- Spec: 1 finding, 0 blocking. The worst is R17, the same-second race, accepted as is.
- Behaviour: 0 findings.
- Smells: 3 findings, 2 blocking. The worst is R13, a test whose expected message picks its setup.
- Names: 0 findings.
- No design questions.

Verdict: changes needed
