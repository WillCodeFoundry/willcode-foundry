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

### Amended after the verdict (the human)
- R15 is Blocking, not a Follow-up: the human decided it in the reviewer's session. Its direction is unchanged.
  So round 4 has three Blocking findings: R13, R14 and R15. The verdict stays the same.

Verdict: changes needed

## Round 5 (reviewing ac110e0)

No "TASK.md changed by another role" or "PLAN.md changed by another role" finding. Reviewed against TASK.md at
cf2da31, signed by the planner's identity, which the architect shares, so a change by the architect can't be told
apart from one by the planner. PLAN.md is unchanged since it was approved at 6694061, signed by the dev. This round
reviews the fixes `df11854...ac110e0` (eb1b6b0, ac110e0). No human change to TASK.md waits to be folded in.

Earlier findings:
- R13: closed. The parametrize table at `tests/test_task_command.py:161-168` pairs each setup function with its
  expected error, and the body only calls the setup it is given (:172).
- R14: closed. `ProjectRepository.seeded_task_notes_dirs` (`tests/support/project_repository.py:70`) is built from
  `open_task` and `closed_task`. Both hand-spelled constants are gone.
- R15: closed. `tests/test_project_tasks.py:170-178` puts each case's `take_task_ids` arguments in the table, with the
  same ids.
- R16: closed. `src/foundry/commands/task.py:33-34` names both refusals without TASK, in the glossary's words.
- R17: accepted as is (round 4).

### Standards
No new findings. `ProjectRepository`'s docstring is still true, and CONTRIBUTING.md asks for shared test setup in
`tests/support/`, which the R14 fix follows. README and the module docstring of `commands/task.py` still match.

### Spec
No findings. The fixes keep every criterion shown with the same tests and ids. AC2: the `[open|closed|branch]` table.
AC5 and AC6 on the CLI: `[no-task-id|tie]`, with the same errors and the `for-each-ref` check. AC1 and AC7: the
seeded dirs give the same paths as before. AC10: the TASK argument is unchanged, and the description adds only what
AC5 and AC6 say. PLAN.md doesn't set the description's text, so it doesn't depart from the plan. No scope creep.

### Behaviour
No findings. In a throwaway clone at ac110e0, the host tier, ruff and mypy pass. The class attribute is a plain
tuple of `str`s built from attributes above it, with the same paths as before. The parametrize data is never changed,
so nothing leaks between tests. `foundry task create --help` renders the new description. Mutations each fail their
own case: not counting closed dirs fails `[closed]` and `[tie]`, not counting branches fails `[branch]` and `[tie]`,
disabling the tie check fails `[tie]`, and changing the no-task-id message fails `[no-task-id]`.

### Smells
Functions the fix diff adds or changes:
- `src/foundry/commands/task.py:add_parser` is clean (only the description text changed).
- `tests/support/project_repository.py`: `ProjectRepository.seeded_task_notes_dirs` is new, clean.
- `tests/test_project_tasks.py`: `take_task_ids` and `test_the_highest_taken_number_counts_whichever_kind_holds_it`
  are clean.
- `tests/test_task_command.py`: `test_create_without_a_task_creates_the_next_one`,
  `test_create_without_a_task_that_can_t_pick_one_…` and `test_a_create_that_loses_the_race_…` are clean.
  `take_no_task_id` is new, clean. `tie_two_task_prefixes` is new (R18).

Findings:
- R18 (Follow-up), possible python-smells 6, copying instead of finding the seam:
  `tests/test_task_command.py:154-158`.
  - What: `tie_two_task_prefixes` writes a notes path by hand, removes the seeded dirs and makes a `task/` branch. That
    is the work `take_task_ids` (`tests/test_project_tasks.py:142`) does with `closed_ids` and `branch_ids`. The same
    hand-built setup is at `tests/test_task_command.py:137-141` and :188-190.
  - Why only a Follow-up: the fix moved setup that was already inline into a function. It didn't introduce the copy.
  - Who hits it: whoever next changes how a test takes a task id. They edit three places here as well as the helper.
  - Direction: move `take_task_ids` into `tests/support/` and call it from both test files.

### Names
Names the fix adds: `seeded_task_notes_dirs`, `take_no_task_id`, `tie_two_task_prefixes`, the `taken` parameter and
the description's prose are clean. "Task prefix" is never bare "prefix". The parametrize parameter `take_task_ids` is
R19. PLAN.md's Names section names none of these test helpers.

- R19 (Blocking), a homonym that misleads at its use: `tests/test_task_command.py:162`, used at :170 and :172.
  - What: `tests/test_project_tasks.py:142` defines the helper `take_task_ids(project_repository, *, open_ids=…, …)`.
    Called with only the repository, it removes the seeded tasks and takes nothing. At
    `tests/test_task_command.py:172`, the same text `take_task_ids(project_repository)` calls a parameter that holds
    one of two setups: one deletes `agent-notes`, the other ties two task prefixes.
  - Who hits it: anyone who greps `take_task_ids` to change or reuse the helper lands on :172. They will read it as
    the helper with its defaults, and think the tie case takes no ids. If R18 is taken, the helper is imported into
    this file and the parameter shadows it.
  - Direction: name the parameter for its role in this test, not the helper's verb.

### Summary
- Standards: 0 findings.
- Spec: 0 findings.
- Behaviour: 0 findings.
- Smells: 1 finding, 0 blocking. The worst is R18, the setup copied beside `take_task_ids`.
- Names: 1 finding, 1 blocking. The worst is R19, the parameter that reads as the helper `take_task_ids`.
- No design questions.

Verdict: changes needed

## Round 6 (reviewing 59c516a)

No "TASK.md changed by another role" or "PLAN.md changed by another role" finding. Reviewed against TASK.md at
cf2da31, signed by the planner's identity, which the architect shares, so a change by the architect can't be told
apart from one by the planner. PLAN.md is unchanged since it was approved at 6694061, signed by the dev. This round
reviews the fix `ac110e0...59c516a` (59c516a): a rename of one parametrize parameter in `tests/test_task_command.py`,
3 lines. No human change to TASK.md waits to be folded in.

The fix is three lines, test-only, so this round ran the five axes inline rather than in sub-agents. Their separation
guards against one axis masking another across a large diff, which three renamed lines can't do.

Earlier findings:
- R17: accepted as is (round 4).
- R18: deferred, as the dev's entry 19 says. It stays a Follow-up, with entry 18's.
- R19: closed. The parameter is now `leave_no_next_task_id` (`tests/test_task_command.py:162`, used at :170 and
  :172). `take_task_ids` no longer appears in that file, so a grep for the helper lands only on
  `tests/test_project_tasks.py`.

### Standards
No findings. The fix touches no docstring or doc, and no doc names the parameter.

### Spec
No findings. Test ids `[no-task-id]` and `[tie]` are unchanged, and both pass, so AC5 and AC6 on the CLI are shown as
in round 5. PLAN.md doesn't name the parameter. No scope creep.

### Behaviour
No findings. In a throwaway clone at 59c516a, `uv run pytest` (808 passed), ruff check, ruff format --check and mypy
pass. Both cases of the renamed test pass, each running its own setup.

### Smells
Functions the fix changes:
- `tests/test_task_command.py:test_create_without_a_task_that_can_t_pick_one_says_to_give_it_and_changes_nothing`:
  clean (only the parameter's name changed).

No findings.

### Names
Names the fix adds:
- `leave_no_next_task_id`: clean. Each setup it holds leaves the repository with no next task id to pick, in the
  words of `NoNextTaskIdError` (`src/foundry/task.py:107`) and its docstring. No other name in the repository spells
  it, so it shadows nothing.

No findings.

### Summary
- Standards: 0 findings.
- Spec: 0 findings.
- Behaviour: 0 findings.
- Smells: 0 findings.
- Names: 0 findings.
- No design questions. Follow-ups R18 (deferred) and entry 15's and 18's Follow-up lines stay open.

Verdict: approved

## Round 7 (reviewing 8825173)

No "TASK.md changed by another role" or "PLAN.md changed by another role" finding. Reviewed against TASK.md at
ea6b764 (D4 folded in). It is signed by the planner's identity, which the architect shares, so a change by the
architect can't be told apart from one by the planner. PLAN.md is at 543b724, signed by the dev; the human approved
its D2 and D3 amendments (LOG.md entries 22 and 24). This round reviews what changed since round 6 approved 59c516a:
83a4dfc (D2), the conflict resolutions of the merge a8a2f54, and 8825173 (D3). No human change to TASK.md waits to be
folded in.

Earlier findings:
- R17: accepted as is (round 4).
- R18: deferred (round 6). It stays a Follow-up.
- No other finding was open.

### Standards
- R20 (Blocking): PLAN.md at 543b724, Approach, lines 4-7.
  - What: the Approach still says `next_task_id` "parses each id with the task id pattern, ignores what doesn't match
    it". It also says `taken_task_ids()` "returns the names taken by task branches and by the dirs".
  - Why it matters: since D3, the plan's own Steps 2 and 3 and the code say otherwise. `src/foundry/task.py:129`
    refuses a name that isn't a task id, and `src/foundry/project_tasks.py:138` keeps only task ids. The plan
    contradicts itself and the code.
  - Who hits it: a dev or reviewer who reads the Approach first, in a later round or a later task. They would expect
    an invalid name to be skipped silently.
  - Direction: amend those two clauses to match Steps 2 and 3, as `Amended: D3`.
  - Shares its cause with R22.
- R21 (Follow-up): `src/foundry/project_tasks.py:12-13`, "the write's own checks and its atomic push refuse what
  changed in between".
  - What: `create_task` fetches `NOTES_BRANCH` again and writes on that fetch (`:111`, `:121`). It refuses only a
    change that takes its own task id (`:113-115`, or the push at `:124`). Another task created in between under a
    different id is accepted, and the task prefix count isn't checked again. The sentence also chains its reason
    behind a colon, which AGENTS.md's "Writing" advises against.
  - Who hits it: rarely, a dev adding another read-then-write operation who trusts the module's guarantee.
  - Direction: say, in a sentence of its own, that the write refuses only a change that clashes with its own task.
    The wording is PLAN.md's (Docs), so amend it there too.

### Spec
No Blocking finding and no scope creep. In a throwaway clone at 8825173, `uv run pytest`, ruff check, ruff format
--check and mypy pass. Every test the amended PLAN.md names exists and asserts what it says:

| AC | Tests at 8825173 |
|---|---|
| AC1 | `test_taken_task_ids_are_the_open_closed_and_branch_ones_and_reading_them_changes_nothing`; `test_create_without_a_task_creates_the_next_one` |
| AC2 | `test_the_highest_taken_number_counts_whichever_kind_holds_it` (open, closed, branch) |
| AC3 | `test_the_next_task_id_is_one_more_than_the_highest_padded_to_four_digits` (OS3 too) |
| AC4 | `test_names_that_aren_t_task_ids_are_not_taken_task_ids`; `test_a_taken_name_that_isn_t_a_task_id_is_refused` |
| AC5 | `test_no_next_task_id_when_none_is_taken_or_task_prefixes_tie[none]`; the CLI refusal test's `[no-task-id]` |
| AC6 | `test_the_most_common_task_prefix_wins_and_the_other_task_prefix_s_higher_number_is_ignored`; `test_each_id_is_counted_once`; the unit tie cases; `test_the_task_prefix_most_task_ids_use_is_followed`; `test_a_task_s_branch_and_notes_count_as_one_task_id`; the CLI `[tie]` |
| AC7 | `test_a_create_that_loses_the_race_for_its_id_fails_and_leaves_only_the_winner_s`. It asserts only `error: `, so it holds for either message in TASK.md's D4 Risks line |
| AC8 | `test_create_with_an_empty_task_refuses_it_as_invalid_and_changes_nothing`, plus the existing create tests, unchanged |
| AC9 | README's table row and task id line; `tests/test_docs.py` |
| AC10 | `test_create_s_task_is_optional_and_its_help_says_what_is_picked_without_it` |
| AC11 | ruff and the host tier, above |

AC4's `wcf-0006` is shown in two parts, `taken_task_ids` then `next_task_id`, exactly as the amended plan splits it.

- R22 (Follow-up): the approved PLAN.md contradicts itself. Its Approach says `next_task_id` ignores what doesn't
  match, but Step 2 (D3) says such a name is refused. The code follows Step 2 (`src/foundry/task.py:129`), and
  `test_a_taken_name_that_isn_t_a_task_id_is_refused` shows it, so the behaviour is right. Shares its cause with R20.

### Behaviour
No findings. In a throwaway clone at 8825173, the host tier, ruff and mypy pass. The changed code was driven through
`ProjectTasks.in_scratch_clone` on bare repositories in odd states:
- Branch names that aren't task ids (`task/wcf-0009/x`, `task/WCF-0099`, `task/wcf-0042x`, `tasks/wcf-0050`) are not
  taken.
- Notes dirs that aren't task ids (trailing space, `-0005`, `wcf-0005.bak`, `Wcf-0010`, a file named like a task) are
  left out, and `next_task_id`'s strict check never sees them.
- With no `agent-notes`, branch-only ids pick the majority task prefix and create `agent-notes` as an orphan.
- An id with 21 digits works.
- With nothing taken, create refuses with the "Give TASK" hint and leaves only `main`.
- `create PROJECT ""` is refused as an invalid id and writes nothing.
- A given TASK never reads the taken ids.

The second read of the branches (once in `taken_task_ids`, once in `create_task`) is the race TASK.md's D4 Risks line
records, and `create_task`'s checks and atomic push still refuse it.

### Smells
Functions the fix changes:
- `src/foundry/commands/task.py:create_main`: clean. It is simpler than at 59c516a and has no branch (DR7).
- `src/foundry/commands/task.py:task_id_to_create`: new, clean.
- `src/foundry/commands/task.py:pick_next_task_id`: clean.
- `src/foundry/project_tasks.py:ProjectTasks.create_task`: clean. It is byte for byte as at 492f4b5.
- `src/foundry/project_tasks.py:ProjectTasks.taken_task_ids`: new, R25.
- `src/foundry/project_tasks.py` (module docstring): clean, apart from R21 on the Standards axis.
- `src/foundry/task.py:Task.__post_init__`: R24.
- `src/foundry/task.py:is_task_id`: new, clean.
- `src/foundry/task.py:_require_task_id`: new, R24.
- `src/foundry/task.py:next_task_id`: clean. Refusing a name that isn't a task id is better than skipping it silently.
- `tests/test_task.py`: `test_a_taken_name_that_isn_t_a_task_id_is_refused` (new) and
  `test_no_next_task_id_when_none_is_taken_or_task_prefixes_tie`: clean.
- `tests/test_task_command.py`: `test_create_without_a_task_creates_the_next_one` and
  `test_create_with_an_empty_task_refuses_it_as_invalid_and_changes_nothing` (new): clean.
- `tests/test_project_tasks.py`: `test_taken_task_ids_are_the_open_closed_and_branch_ones_and_reading_them_changes_nothing`,
  `test_names_that_aren_t_task_ids_are_not_taken_task_ids` and `test_without_task_branches_or_notes_no_task_id_is_taken`
  are clean. `test_the_highest_taken_number_counts_whichever_kind_holds_it`,
  `test_the_task_prefix_most_task_ids_use_is_followed` and `test_a_task_s_branch_and_notes_count_as_one_task_id` are
  R23.
- The merge's conflict resolutions in a8a2f54 only join imports and codemap rows: clean.

Findings:
- R23 (Follow-up), possible python-smells 10, tests that prove nothing new: `tests/test_project_tasks.py:166`,
  `:183` and `:189`.
  - What: since D2 these check `next_task_id(taken_task_ids())`, so they repeat rules that `tests/test_task.py`
    already proves. `:153` already shows each kind of id is taken. `:189` can't fail for the reason its name gives,
    since `taken_task_ids` returns a frozenset.
  - Who hits it: the next dev who changes how `next_task_id` picks gets failures in the `ProjectTasks` tests too.
  - Direction: assert on `taken_task_ids()` alone. PLAN.md's Tests name these, so that is a plan change.
- R24 (Follow-up), possible python-smells 5.1, validate-and-fetch: `src/foundry/task.py:108`. `_require_task_id` is
  named as a check but returns the parsed match. `Task.__post_init__` (`:67`) calls it only for its error. Shares its
  cause with R26.
- R25 (Follow-up), python-smells 8, narrating: `src/foundry/project_tasks.py:128`, "for next_task_id", names a
  caller and goes stale when another appears. Direction: drop the phrase.

### Names
Names the fix adds or changes:
- `ProjectTasks.taken_task_ids`: clean. Since D3 it returns only task ids, as its name says, and it matches PLAN.md.
- `pick_next_task_id`, `task_id_to_create`: clean, as PLAN.md names them.
- `is_task_id`: clean. Its docstring says "task prefix", the glossary's word.
- `_require_task_id`: R26.
- `next_task_id`, which now refuses a name that isn't a task id: clean. A computation may refuse bad input.
- `create_task`: clean, back to main's.
- Locals `taken`, `branches`, `notes_branch`, `matches`: clean. `notes_branch` is the existing name for a
  `FetchedBranch`.
- The three new test names: clean.
- The added prose (module docstring, docstrings, the ARCHITECTURE.md row and the merge's resolution): clean. It uses
  no _Avoid_ word and no bare "prefix".

Findings:
- R26 (Blocking): `src/foundry/task.py:108`, `_require_task_id(task_id) -> re.Match[str]`, used at `:129` as
  `matches = [_require_task_id(taken_id) …]`.
  - What: python-naming-smells, "promises less than it does". `require` is a word the project agrees on: each of the
    other 13 `require_`/`_require_` functions in `src/` returns None and only checks, for example
    `_require_no_task` (`src/foundry/project_tasks.py:268`) and `require_valid_handoff_args`
    (`src/foundry/commands/task.py:196`). This one also parses.
  - Who hits it: the next reader of `next_task_id`, at `:129`, who has to open the definition to learn that a check
    returns the parse.
  - Direction: name it for what it returns, a parse that refuses, or split the check from the parse.
  - This is a plan change. PLAN.md (Step 2, Names) gives the name and signature, so the dev amends the plan first.
  - Shares its cause with R24.

### Summary
- Standards: 2 findings, 1 Blocking. Worst: R20, PLAN.md's Approach contradicts its own Steps and the code.
- Spec: 1 finding, 0 Blocking. Worst: R22, the same contradiction, judged by the Spec bar.
- Behaviour: 0 findings.
- Smells: 3 findings, 0 Blocking. Worst: R23, the `ProjectTasks` tests re-prove `next_task_id`.
- Names: 1 finding, 1 Blocking. Worst: R26, `_require_task_id` returns a value, unlike every other `require_`.
- No design questions. R18 (deferred) and the earlier Follow-up lines stay open.

Verdict: changes needed

## Round 8 (reviewing d73140a)

No "TASK.md changed by another role" or "PLAN.md changed by another role" finding. Reviewed against TASK.md at
ea6b764. It is signed by the planner's identity, which the architect shares, so a change by the architect can't be
told apart from one by the planner. PLAN.md is at a53b8d4, signed by the dev, with the R20, R21, R23 and R26
amendments the human approved (LOG.md entry 29). This round reviews the fix diff `8825173...d73140a`. Its only task
commit is d73140a; 6905030 is a clean merge of origin/HEAD that brings kit and template docs only. No human change to
TASK.md waits to be folded in.

Earlier findings:
- R17: accepted as is (round 4).
- R18: deferred (round 6). It stays a Follow-up.
- R20: closed. PLAN.md's Approach (a53b8d4) now says `next_task_id` refuses a name that isn't a task id, and
  `taken_task_ids` returns only task ids. This matches Steps 2 and 3 and the code.
- R21: closed. `src/foundry/project_tasks.py:12-13` now puts the point in a sentence of its own, word for word as
  PLAN.md's Docs. R27 below is a smaller point in the new sentence.
- R22: closed, with R20.
- R23: closed. AC2's test asserts on `taken_task_ids()` alone, and the two tests that re-proved `next_task_id` are
  gone, as the amended plan says. R28 below is about what is left.
- R24: closed, with R26. `Task.__post_init__` calls a parse for its refusal, which is ordinary parse-to-validate.
- R25: closed. "for next_task_id" is gone from `src/foundry/project_tasks.py:128`.
- R26: closed. `_parse_task_id` (`src/foundry/task.py:108`) is named for what it returns. It matches the other
  parse functions in `src/` (`config.parse`, `parse_fingerprint`) and PLAN.md's Step 2 and Names.
  `git grep -w _require_task_id` finds nothing.

### Standards
R20, R21 and R22 are closed, as above. PLAN.md at a53b8d4 no longer contradicts itself or the code. The docstrings of
`task.py`, `project_tasks.py` and `take_task_ids` are true after the fix.
- R27 (Follow-up): `src/foundry/project_tasks.py:12-13`, "its own checks and atomic push refuse only a change that
  clashes with its own task".
  - What: the checks refuse only a clash, but the push doesn't. `push_atomic` is never forced
    (`src/foundry/project_scratch_clone.py:182`). So any commit to `NOTES_BRANCH` between `create_task`'s own fetch
    (`:111`) and its push (`:124`) gets the push rejected, even one for another task. The sentence holds for the gap
    it is about, between `taken_task_ids` and `create_task`'s fetch, but "only" overstates the push.
  - Who hits it: rarely, a dev adding another read-then-write operation who reasons about concurrent writes from this
    sentence.
  - Direction: say that the checks refuse only a clash with its own task, and the push refuses any change since the
    write's own fetch. PLAN.md's Docs has the same wording, so amend it there too. Or accept as is.

### Spec
No finding and no scope creep. R22 and R23 are closed. In a throwaway clone at d73140a, `uv run pytest`, ruff check,
ruff format --check and mypy pass. The code matches PLAN.md at a53b8d4: its names, its errors, its docstring sentence
and its tests.

| AC | Tests at d73140a |
|---|---|
| AC1 | `test_taken_task_ids_are_the_open_closed_and_branch_ones_and_reading_them_changes_nothing`; `test_create_without_a_task_creates_the_next_one` |
| AC2 | `test_a_task_id_is_taken_whichever_kind_holds_it[open,closed,branch]`; `test_the_next_task_id_is_one_more_than_the_highest_padded_to_four_digits`; `test_create_without_a_task_creates_the_next_one` |
| AC3 | `test_the_next_task_id_is_one_more_than_the_highest_padded_to_four_digits` (OS3 too) |
| AC4 | `test_names_that_aren_t_task_ids_are_not_taken_task_ids`; `test_a_taken_name_that_isn_t_a_task_id_is_refused` |
| AC5 | `test_no_next_task_id_when_none_is_taken_or_task_prefixes_tie[none]`; `test_without_task_branches_or_notes_no_task_id_is_taken`; the CLI refusal test's `[no-task-id]` |
| AC6 | `test_the_most_common_task_prefix_wins_and_the_other_task_prefix_s_higher_number_is_ignored`; `test_each_id_is_counted_once`; the unit tie cases; the CLI `[tie]`. That a branch and its notes count once also rests on `taken_task_ids` returning a frozenset, and on the AC1 test |
| AC7 | `test_a_create_that_loses_the_race_for_its_id_fails_and_leaves_only_the_winner_s` |
| AC8 | `test_create_with_an_empty_task_refuses_it_as_invalid_and_changes_nothing`, plus the existing create tests, unchanged |
| AC9 | README's table row and task id line; `tests/test_docs.py` |
| AC10 | `test_create_s_task_is_optional_and_its_help_says_what_is_picked_without_it` |
| AC11 | ruff and the host tier, above |

AC2 is shown in three parts, as the amended plan splits it: each kind of id is taken, `next_task_id` follows the
highest number, and the CLI test composes the two.

### Behaviour
No findings. The fix is a rename, two docstring edits and removed tests, so it changes no path. In a throwaway clone
at d73140a:
- The host tier, ruff and mypy pass.
- `foundry task create --help` still shows `PROJECT [TASK]`.
- `_require_task_id` appears nowhere, in code, tests or docs.
- `Task` and `next_task_id` still refuse a name that isn't a task id.

### Smells
Functions the fix changes:
- `src/foundry/task.py:Task.__post_init__`: clean.
- `src/foundry/task.py:_parse_task_id`: clean. It was only renamed.
- `src/foundry/task.py:next_task_id`: clean.
- `src/foundry/project_tasks.py` (module docstring): clean, apart from R27 on the Standards axis.
- `src/foundry/project_tasks.py:ProjectTasks.taken_task_ids` (docstring): clean.
- `tests/test_project_tasks.py:take_task_ids`: clean. It is simpler without `keep_seeded`.
- `tests/test_project_tasks.py:test_a_task_id_is_taken_whichever_kind_holds_it`: R28.
- `tests/test_project_tasks.py:test_the_task_prefix_most_task_ids_use_is_followed`: removed.
- `tests/test_project_tasks.py:test_a_task_s_branch_and_notes_count_as_one_task_id`: removed.

Findings:
- R28 (Follow-up), possible python-smells 10, a test that proves little new: `tests/test_project_tasks.py:157-169`.
  - What: now that it asserts on `taken_task_ids()` alone, it largely repeats `:150-153`, which already shows that
    open, closed and branch ids are taken. Only its `open` case, with two open dirs, adds anything.
  - Who hits it: the next dev who breaks reading one kind of id gets two failures for one fault. Rarely.
  - Direction: accept as is. The human-approved PLAN.md (Tests, AC2) names this test, so folding it into `:153`
    would be a plan change.

### Names
Names the fix adds or changes:
- `_parse_task_id`: clean. It is named as PLAN.md gives it, and it reads right at `src/foundry/task.py:129`.
- `test_a_task_id_is_taken_whichever_kind_holds_it`: clean. It now names what it asserts.
- `take_task_ids`, with `keep_seeded` removed: clean.
- The added prose in `project_tasks.py:12-13` and `:128`: clean. It uses no _Avoid_ word and no bare "prefix".

No findings. R26 is closed, as above.

### Summary
- Standards: 1 finding, 0 Blocking. Worst: R27, the new docstring sentence overstates what the push refuses.
- Spec: 0 findings.
- Behaviour: 0 findings.
- Smells: 1 finding, 0 Blocking. Worst: R28, AC2's test largely repeats AC1's.
- Names: 0 findings.
- No design questions. R18, R27 and R28 stay open as Follow-ups.

Verdict: approved
