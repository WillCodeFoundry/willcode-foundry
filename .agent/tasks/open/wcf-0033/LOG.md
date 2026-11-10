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

## 9 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0033 (already up to date). Revised PLAN.md for plan round 1; each changed
line ends `Amended: R<n>`. No code yet.
- Answers R1, R8: the TASK help and the README sentence now say the next id follows the task prefix most of the
  project's task ids use, and that ids with other prefixes are ignored (PLAN.md Docs), as entry 8 asks.
- Answers R7: as entry 7 answers it, `BRANCH_PREFIX` stays; the regex group, `next_task_id`'s locals and the tie
  error say `task_prefix` / "task prefix", and GLOSSARY.md's **Task id** gets bare "prefix" under _Avoid_ (Steps 1–3,
  Names, Errors, Docs).
- Answers R2: `task.py`'s module docstring and its codemap row are in the Docs list.
- Answers R3: the Docs list names the `project_tasks.py:5-6` sentence and how it changes.
- Answers R4: the AC7 test asserts the final tips of `agent-notes` and the task branch equal the competitor's.
- Answers R5: the AC1 method test asserts the commit subject `Add task wcf-0034`.
- Answers R6: the AC5/AC6 CLI test's setup is named: `agent-notes` deleted for AC5; seeded tasks removed for AC6.
Next: on plan approval, step 1 of PLAN.md, the refactor in `task.py`.

## 10 · reviewer · plan-changes
Done: plan round 2 on PLAN.md at 97f5e0c, against TASK.md at cf2da31. The history of both files is clean. R1–R8
are closed. One new finding blocks: R9, where the planned README id line and GLOSSARY definition say bare "prefix",
which the plan's own _Avoid_ entry bans. R12 shares its cause. The follow-ups R10 (AC7 test setup), R11 (the
docstring says branches come from a fetch) and R12 are in REVIEW.md, round 2. No design questions.
Next: the dev revises PLAN.md for R9, and any follow-ups it takes, then ends with plan-ready.

## 11 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0033 (already up to date). Revised PLAN.md for plan round 2; each changed
line ends `Amended: R<n>`. No code yet.
- Answers R9: the README task id line and the GLOSSARY **Task id** definition now say "a task prefix of lowercase
  ASCII letters"; no planned prose says bare "prefix" for a task id's letters (PLAN.md Docs).
- Answers R12: "ids with other task prefixes" in the README sentence and the TASK help, and "task prefix" in the
  D1 test's description (PLAN.md Docs, Tests).
- Answers R10: the AC7 test's setup is named: seeded tasks removed and `wcf-0030` open, so both creates pick
  `wcf-0031` (PLAN.md Tests, AC7).
- Answers R11: the `project_tasks.py` docstring says the dirs come from one fetch of `NOTES_BRANCH` and the task
  branches from the remote's branch list (PLAN.md Docs).
Next: on plan approval, step 1 of PLAN.md, the refactor in `task.py`.

## 12 · reviewer · plan-approved
Done: plan round 3 on PLAN.md at 6694061, against TASK.md at cf2da31. The history of both files is clean. R9–R12
are closed, with no new findings on any axis and no design questions. No human change to TASK.md is waiting to
be folded in. Verdict: plan approved at 6694061.
Next: the dev starts step 1 of PLAN.md, the refactor in `task.py`, then ends with ready-for-review.

## 13 · dev · progress
Done: merged origin/HEAD into task/wcf-0033 (already up to date). Steps 1–4 of PLAN.md in ac5b7e0: `BRANCH_PREFIX`,
the `task_prefix`/`number` groups, `next_task_id` and `NoNextTaskIdError` in `task.py`; `create_next_task` sharing
`_create` with `create_task` in `project_tasks.py`; TASK optional on `foundry task create`. Tests for AC1–AC8 and
AC10 at the seams PLAN.md names; ruff, mypy, vulture, pylint and the host tier (808 passed) pass.
- `_create` checks a given id before any git call, as `create_task` did, so AC8 holds for an invalid id too.
- The AC7 test gives the competing create another `GIT_COMMITTER_DATE`. Two creates of one id by one identity in the
  same second make the very same commit, so the second push changes nothing and succeeds.
Next: step 5, the docs (README, GLOSSARY, ARCHITECTURE, docstrings already done), then the draft PR.

## 14 · dev · ready-for-review
Done: PLAN.md's steps 1–5 are in ac5b7e0 (code and tests) and df11854 (docs: README, GLOSSARY **Task id** with bare
"prefix" under _Avoid_, ARCHITECTURE codemap, `create_task`'s docstring). Draft PR:
https://github.com/WillCodeFoundry/willcode-foundry/pull/80. Its CI passes, the docker tier included. Locally, ruff,
mypy, vulture, pylint and `uv run pytest --cov` pass (808 passed).
- [x] AC1: `test_the_next_task_is_created_as_create_task_would_create_it` (tests/test_project_tasks.py);
  `test_create_without_a_task_creates_the_next_one` (tests/test_task_command.py).
- [x] AC2: `test_the_highest_taken_number_counts_whichever_kind_holds_it[open|closed|branch]`.
- [x] AC3: `test_the_next_task_id_is_one_more_than_the_highest_padded_to_four_digits` (tests/test_task.py).
- [x] AC4: `test_names_that_aren_t_task_ids_are_ignored`; `test_task_branches_that_aren_t_task_ids_are_ignored`.
- [x] AC5: `test_no_next_task_id_when_none_is_taken_or_task_prefixes_tie[none|none-valid]`;
  `test_with_no_task_id_taken_nothing_is_pushed`;
  `test_create_without_a_task_that_can_t_pick_one_says_to_give_it_and_changes_nothing[no-task-id]`.
- [x] AC6: `test_the_most_common_task_prefix_wins_and_the_other_task_prefix_s_higher_number_is_ignored`,
  `test_each_id_is_counted_once`, `…_or_task_prefixes_tie[tie|tie-of-two-of-three]` (tests/test_task.py);
  `test_the_task_prefix_most_task_ids_use_is_followed`, `test_a_task_s_branch_and_notes_count_as_one_task_id`
  (tests/test_project_tasks.py); `…_changes_nothing[tie]` (tests/test_task_command.py).
- [x] AC7: `test_a_create_that_loses_the_race_for_its_id_fails_and_leaves_only_the_winner_s`. The loser's stderr is
  git's `! [rejected] agent-notes -> agent-notes (fetch first)`.
- [x] AC8: every existing create test passes unchanged; `_create` still refuses an invalid given id before git runs.
- [x] AC9: README row and task id line; `tests/test_docs.py` passes.
- [x] AC10: `test_create_s_task_is_optional_and_its_help_says_what_is_picked_without_it`.
- [x] AC11: ruff and the host tier pass, as above.
- For the reviewer: two creates of one id, by one identity in the same second, make the same commit, so the second
  succeeds with nothing to push (LEARNINGS.md). Its result is the same as the first's. The AC7 test avoids it with
  `GIT_COMMITTER_DATE`.
Next: the reviewer's code round.

## 15 · reviewer · changes-needed
Done: code round 4 on df11854, against TASK.md at cf2da31 and PLAN.md as approved at 6694061. The history of both files
is clean. Spec, Behaviour and Names have no blocking finding: every AC is met by code and a test, and the host tier,
ruff and mypy pass. Two Smells findings block, both in the tests: R13 (`tests/test_task_command.py:163` picks its
setup from the expected message) and R14 (`SEEDED_TASK_NOTES_DIRS` spelled twice by hand, where `ProjectRepository`
already names the seeded tasks). Follow-ups R15, R16 and R17 (R17 accepted as is) are in REVIEW.md, round 4. No
design questions, and no human change to TASK.md waits to be folded in.
Next: the dev fixes R13 and R14, answers each by id (and R15, R16 if taken), then ends with ready-for-review.
- Follow-up: src/foundry/project_tasks.py `_read_task_ids` · named and documented as task ids, but returns every dir name unchecked · a new caller could trust them as valid ids.
- Follow-up: tests/test_task_command.py:114-115 and other seed-id literals · `tst-0000` and `cls-0000` spelled by hand beside `ProjectRepository.open_task`/`closed_task` · renaming a seed means editing several test files.

## 16 · reviewer · changes-needed
Done: at the human's word, R15 (`tests/test_project_tasks.py:175` builds its arguments from `kind` with
`f"{kind}_ids"`) is Blocking, not a Follow-up. Appended to REVIEW.md, round 4. Round 4 now has three Blocking findings,
R13, R14 and R15. Follow-ups R16 and R17 are unchanged, and R17 is still accepted as is.
Next: the dev fixes R13, R14 and R15, answers each by id, then ends with ready-for-review.

## 17 · dev · ready-for-review
Done: merged origin/HEAD into task/wcf-0033 (already up to date). Answered code round 4 in eb1b6b0 (tests) and
ac110e0 (create's description). PR https://github.com/WillCodeFoundry/willcode-foundry/pull/80 stays a draft; its CI
passes at ac110e0. Locally ruff, mypy, vulture, pylint and `uv run pytest --cov` pass (808 passed). No human change to
TASK.md waits to be folded in. PLAN.md is unchanged: no name, error, seam or approach moved.
- Answers R13: fixed in eb1b6b0. The refusal test's parametrize table now pairs each case's setup function
  (`take_no_task_id`, `tie_two_task_prefixes`) with its expected error; the body no longer reads the message.
- Answers R14: fixed in eb1b6b0. `ProjectRepository.seeded_task_notes_dirs` is built from `open_task` and
  `closed_task`; both hand-spelled `SEEDED_TASK_NOTES_DIRS` are gone.
- Answers R15: fixed in eb1b6b0. Each case's `take_task_ids` arguments are in the parametrize table; ids unchanged.
- Answers R16: fixed in ac110e0. create's description adds one sentence naming both refusals without TASK.
- Answers R17: accepted as is, as the round says; no change.
- R13 and R14 both touch the refusal test, but they are separate causes (the setup switch; a constant shared by three
  tests), each fixed by a one-place change, so I didn't take it as a cluster needing a PLAN.md revision.
- AC1–AC11 are met by the same tests as entry 14; the renamed parameters keep every test id.
Next: the reviewer's code round 5.

## 18 · reviewer · changes-needed
Done: code round 5 on ac110e0, against TASK.md at cf2da31 and PLAN.md as approved at 6694061. The history of both files
is clean. R13, R14, R15 and R16 are closed, and R17 stays accepted as is. Standards, Spec and Behaviour have no
findings. Locally, ruff, mypy and the host tier pass (808 passed). One new Blocking finding, R19 (Names): the
parametrize parameter `take_task_ids` at `tests/test_task_command.py:162` reads as the helper of the same name in
`tests/test_project_tasks.py`. One new Follow-up, R18 (Smells): `tie_two_task_prefixes` and two other tests rebuild
`take_task_ids`'s setup by hand. No design questions, and no human change to TASK.md waits to be folded in.
Next: the dev renames the parameter for R19, answers R19 (and R18, if taken) by id, then ends with ready-for-review.
- Follow-up: tests/test_project_tasks.py:210 `test_with_no_task_id_taken_nothing_is_pushed` · deletes the notes branch inline, the same step as `take_no_task_id` in tests/test_task_command.py:151 · a third copy to change with the R18 move.

## 19 · dev · ready-for-review
Done: merged origin/HEAD into task/wcf-0033 (already up to date). Answered code round 5 in 59c516a. PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/80 stays a draft; its CI passes at 59c516a. Locally ruff,
mypy, vulture, pylint and `uv run pytest --cov` pass. No human change to TASK.md waits to be folded in. PLAN.md is
unchanged: the renamed parameter is a test-local name that PLAN.md doesn't list.
- Answers R19: fixed in 59c516a. The parametrize parameter is now `leave_no_next_task_id`, named for what each setup
  does, in `NoNextTaskIdError`'s words; `take_task_ids` no longer appears in tests/test_task_command.py.
- Answers R18: deferred, because moving `take_task_ids` into tests/support/ and rewriting three setups across two test
  files is a refactor of setup this task didn't introduce, as the round says. It stays a Follow-up with entry 18's.
- AC1–AC11 are met by the same tests as entries 14 and 17; the rename keeps every test id.
Next: the reviewer's code round 6.

## 20 · reviewer · approved
Done: code round 6 on 59c516a, against TASK.md at cf2da31 and PLAN.md as approved at 6694061. The history of both files
is clean. R19 is closed, R18 deferred as entry 19 says, R17 stays accepted as is. The fix is a three-line test-only
rename, so the five axes ran inline; none has a finding. In a throwaway clone, the host tier (808 passed), ruff and
mypy pass. No design questions are open, no question to the architect waits, and no human change to TASK.md waits to
be folded in.
Next: the dev marks PR https://github.com/WillCodeFoundry/willcode-foundry/pull/80 ready and ends with pr-ready.

## 21 · dev · pr-ready
Done: merged origin/HEAD into task/wcf-0033 (already up to date, so no new commit after the approving round's
59c516a). CI passes at 59c516a. Wrote PR https://github.com/WillCodeFoundry/willcode-foundry/pull/80's title and body
from the `pr` skill and marked it ready. Every review Follow-up is answered: R18 deferred (entry 19), R17 accepted as
is, plan-round ones answered in PLAN.md. AC1–AC11 are met by the tests entries 14, 17 and 19 name.
Next: the human reviews and merges PR 80.

## 22 · dev · progress
Done: the human, in my session after round 6's approval, asked that create without TASK not have its own method:
the entry point picks the next id, then takes the same `create_task` path as a given TASK. PR 80 is back to draft.
- Asks D2 → human: drop `ProjectTasks.create_next_task` and `_create`'s None branch, restoring `create_task`; add a
  read-only `ProjectTasks.taken_task_ids()`; `commands/task.py`'s `pick_next_task_id(project_tasks)` returns
  `next_task_id(project_tasks.taken_task_ids())` with the "Give TASK" hint, and `create_main` calls `create_task` with
  the id. Costs a second fetch of `agent-notes`; a lost race may refuse as "already exists" instead of git's push
  rejection, still exit 1 with nothing written (AC7).
- Answers D2: approved as proposed (the human).
- plan-approved (the human) at the PLAN.md commit that follows this entry; PLAN.md's changed lines say `Amended: D2`.
Next: implement D2 test-first, run the checks, wait for CI, end with ready-for-review.

## 23 · dev · ready-for-review
Done: D2 implemented in 83a4dfc, after round 6's approval of 59c516a, so it goes back for review. PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/80 is a draft again; its CI passes at 83a4dfc. Merged
origin/HEAD first (already up to date). Locally ruff, mypy, vulture, pylint and `uv run pytest --cov` pass.
- `ProjectTasks.create_next_task`, `_create` and `_taken_task_ids` are gone; `create_task` is byte for byte the
  default branch's again. New read-only `ProjectTasks.taken_task_ids()`. `commands/task.py`: `pick_next_task_id`
  replaces the module `create_task`; `create_main` does `task_id = args.task_id or pick_next_task_id(project_tasks)`,
  then `project_tasks.create_task(task_id, template)`.
- Tests: tests/test_project_tasks.py's create_next_task tests now check `taken_task_ids` (AC1's ids, and that
  reading changes no ref; no notes branch gives no ids) and `next_task_id(taken_task_ids())` (AC2, AC4, AC6). The
  AC1 CLI test also asserts the commit subject `Add task wcf-0034`, as amended PLAN.md says. The AC7 race test
  passes unchanged.
- ARCHITECTURE.md's `project_tasks.py` row: "reading the task ids their notes and task branches take" replaces
  "creating them, under an id given or the next one". PLAN.md amended for it (D2).
- AC1–AC11 are met by the tests PLAN.md names as amended for D2; the rest as in entries 14, 17 and 19.
Next: the reviewer's code round 7, on 83a4dfc.

## 24 · dev · progress
Done: merged origin/HEAD into task/wcf-0033 in a8a2f54 (PRs 81, wcf-0034's `task show`, and 82). Conflicts, each kept
both sides: ARCHITECTURE.md's `task.py` and `project_tasks.py` rows (this task's `next_task_id` and taken task ids,
beside main's "turn and its log's last entry"); `project_tasks.py`'s `foundry.task` import (`BRANCH_PREFIX` and
`TURN_FILE`); `tests/test_task_command.py`'s imports (both sides' modules and helpers). Checks pass.
The human reviewed 83a4dfc in my session and decided the changes below. The amended PLAN.md lines say `Amended: D3`.
- Asks D3 → human: (1) `create PROJECT ""` now picks the next id, since `args.task_id or …` treats `''` as left
  out, breaking AC8; (2) `taken_task_ids` returns invalid names; (3) the `project_tasks.py` docstring says a write
  "writes on what it read", which `taken_task_ids` then `create_task` doesn't.
- Answers D3: (1) a `commands/task.py` function checks `task_id is not None`, returning it or
  `pick_next_task_id(project_tasks)`, so `create_main` has no branch (DR7); a test that `create PROJECT ""` exits 1
  with the invalid-id refusal and changes no ref. (2) `taken_task_ids` keeps only valid task ids, parsed in
  `task.py` (DR1); `next_task_id` assumes valid ids; AC4's tests move to `taken_task_ids`. (3) one sentence: a write
  may follow a separate earlier read, since its own checks and atomic push refuse what changed. R17 and R18 stay as
  they are. The PLAN.md amendments for these are approved (the human).
- Asks D4 → planner: TASK.md's Risks line "A race's refusal shows git's push rejection, not 'already exists'" no
  longer holds since D2: a lost race shows either git's push rejection or create_task's "already exists"; exit 1
  with nothing written still holds (AC7).
- Answers D4: change the Risks line to say either message can appear, exit 1 with nothing written (the human).
- plan-approved (the human) at the PLAN.md commit that follows this entry.
Next: implement D3 test-first, run the checks and CI, then end with task-question so the planner folds D4 into TASK.md
before round 7.

## 25 · dev · task-question
Done: D3 implemented in 8825173; CI passes on it, and locally ruff, mypy, vulture, pylint and `uv run pytest --cov`
pass. PR https://github.com/WillCodeFoundry/willcode-foundry/pull/80 stays a draft; its body now reflects D2 and D3.
- (1) `commands/task.py`'s `task_id_to_create(project_tasks, task_id)` returns `task_id` unless it is None, else
  `pick_next_task_id`'s; `create_main` has no branch. Test:
  `test_create_with_an_empty_task_refuses_it_as_invalid_and_changes_nothing` (AC8).
- (2) `task.py`: `is_task_id` and `_require_task_id` (which `Task.__post_init__` now calls, same message);
  `next_task_id` refuses a name that isn't a task id. `taken_task_ids` filters with `is_task_id`. AC4 tests:
  `test_names_that_aren_t_task_ids_are_not_taken_task_ids` (tests/test_project_tasks.py, branches and a notes dir),
  `test_a_taken_name_that_isn_t_a_task_id_is_refused` (tests/test_task.py); the "none-valid" case is gone.
- (3) `project_tasks.py`'s module docstring has the sentence, word for word as PLAN.md says.
- R17, R18: unchanged, as the human said.
- Commits after round 6's approval of 59c516a: 83a4dfc (D2), a8a2f54 (merge of origin/HEAD), 8825173 (D3).
Ending with task-question, not ready-for-review: D4 is a TASK.md change the human decided that TASK.md doesn't hold
yet, and AGENTS.md says to hand it to the planner before review.
- Asks D4 → planner: fold D4 (entry 24) into TASK.md's Risks: a lost race shows git's push rejection or
  "task … already exists"; exit 1 with nothing written still holds. Then hand the task to the reviewer for round 7
  on 8825173, which covers D2 and D3 too.
Next: once TASK.md holds D4, the reviewer's code round 7 on 8825173.

## 26 · planner · planned
Done: folded the human's answer to D4 (entry 24) into TASK.md in ea6b764. The Risks line now says a lost race
refuses with either git's push rejection or "task … already exists", and either way create exits 1 with nothing of its
own written. It ends `Amended: D4`. AC7 and OS5 still hold as they are, and no other line changed.
- Answers D4: TASK.md amended in ea6b764 (Risks); no criterion changed.
Next: the dev ends with ready-for-review so the reviewer runs code round 7 on 8825173, which covers D2, D3 and D4.

## 27 · dev · ready-for-review
Done: merged origin/HEAD into task/wcf-0033 (already up to date, no new commit). Locally ruff (check and format),
mypy, vulture, pylint and `uv run pytest --cov` (97.34%) pass on 8825173; PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/80 is a draft at 8825173 and its CI passes (lint, mypy,
sandbox-image, test 3.11 and 3.14). TASK.md holds D4 since ea6b764; no other human-decided change is pending.
- Commits after round 6's approval of 59c516a: 83a4dfc (D2), a8a2f54 (merge of origin/HEAD, conflicts listed in
  entry 24), 8825173 (D3).
- AC1–AC11 are met by the tests PLAN.md names as amended for D2 and D3, as entries 23 and 25 list.
Next: the reviewer's code round 7 on 8825173, covering D2, D3, the merge in a8a2f54, and TASK.md's D4 amendment.

## 28 · reviewer · no-agreement
Done: code round 7 on 8825173, in REVIEW.md. It covers D2 (83a4dfc), the merge a8a2f54's conflict resolutions, D3
(8825173) and TASK.md's D4 amendment (ea6b764). The host tier, ruff and mypy pass in a throwaway clone, and every
AC has the test REVIEW.md's table names. Behaviour found nothing. 2 Blocking findings (R20, R26) and 5 Follow-ups
(R21–R25). No design question.
This is the fourth code round (4, 5, 6, 7), and Blocking findings are open after it. ROLE.md says to end with
no-agreement rather than send it back for another round, even though the dev hasn't answered these yet. There is no
disagreement on record; both are new since D2 and D3.
- Asks R20 → human: PLAN.md's Approach (543b724, lines 4-7) still says `next_task_id` ignores names that aren't task
  ids, and that `taken_task_ids` returns names. Since D3, Steps 2 and 3 and the code say the opposite. Should the dev
  amend those two clauses as `Amended: D3` (my direction), or do you accept the plan as is?
- Asks R26 → human: `_require_task_id` (`src/foundry/task.py:108`) returns the parsed match. Every other `require_`
  function in `src/` (13 of them) returns None and only checks. You approved the name in D3. Should the dev rename it
  as a parser, which is a PLAN.md change, or do you accept it as is?
- If you send it back for the fixes, the dev could take the cheap Follow-ups in the same pass: R21 (a docstring
  overstates what create_task refuses), R22 (shares R20's cause) and R25.
- Follow-up: src/foundry/project_tasks.py:268 `_require_no_task` · uses TaskNotFoundError for normal flow · a check that reads as two jobs; the next reader must follow the exception to see the happy path.
Next: the human answers R20 and R26. Then the dev fixes them, or the human accepts them, and ends with
ready-for-review or pr-ready as the human decides.

## 29 · reviewer · changes-needed
Done: the human answered round 7's questions in my session: fix every finding from that round.
- Answers R20: amend PLAN.md's Approach (lines 4-7) to match Steps 2 and 3 and the code, as `Amended: D3`. Two
  points: `next_task_id` refuses a name that isn't a task id, and `taken_task_ids` returns only task ids
  (the human).
- Answers R26: rename `_require_task_id` for what it does, a parse that refuses a name that isn't a task id. Amend
  PLAN.md's Step 2 and Names to the new name first (the human).
- The human also wants round 7's Follow-ups fixed in this pass: R21, R22 (fixed with R20), R23, R24 (fixed with
  R26) and R25. R21's sentence and R23's tests are PLAN.md's wording (Docs, Tests), so amend the plan for them too.
  R18 and the earlier Follow-up lines stay as they were.
Next: the dev amends PLAN.md for R20, R21, R23 and R26, which the human approved here. The dev then fixes R20–R26
test-first, answers each by its id, and ends with ready-for-review for round 8.

## 30 · dev · progress
Done: merged origin/HEAD into task/wcf-0033 in 6905030 (PR 83, kit docs only; no conflicts). Amended PLAN.md for R20
(Approach), R21 (Docs), R23 (Tests: AC2, the most common task prefix, each id counted once) and R26 (Step 2, Names:
`_parse_task_id`), each line `Amended: R<n>`, as the human approved in entry 29.
- plan-approved (the human, entry 29) at the PLAN.md commit that follows this entry.
Next: fix R21, R23, R24/R26 and R25 in code, run the checks and CI, answer R20–R26, end with ready-for-review.

## 31 · dev · ready-for-review
Done: round 7's findings fixed in d73140a, on PLAN.md as amended in a53b8d4 (entry 30). Locally ruff (check and
format), mypy, vulture, pylint and `uv run pytest --cov` (97.34%) pass; PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/80 is a draft at d73140a and its CI passes.
- Answers R20: fixed in a53b8d4 (PLAN.md's Approach, `Amended: R20`).
- Answers R21: fixed in d73140a; PLAN.md's Docs amended to the same sentence in a53b8d4.
- Answers R22: fixed in a53b8d4, with R20.
- Answers R23: fixed in d73140a. AC2's test is now `test_a_task_id_is_taken_whichever_kind_holds_it` and asserts
  `taken_task_ids()` alone; `test_the_task_prefix_most_task_ids_use_is_followed` and
  `test_a_task_s_branch_and_notes_count_as_one_task_id` are gone, as asserting `taken_task_ids()` alone would only
  repeat AC1's and AC2's tests. `take_task_ids` lost its then-unused `keep_seeded`. PLAN.md's Tests amended (a53b8d4).
- Answers R24: fixed in d73140a, with R26: as `_parse_task_id`, `Task.__post_init__` calls a parse that refuses.
- Answers R25: fixed in d73140a ("for next_task_id" dropped).
- Answers R26: fixed in d73140a, `_require_task_id` renamed `_parse_task_id`; PLAN.md's Step 2 and Names amended
  first (a53b8d4). `git grep -n -w _require_task_id` finds nothing.
- Commits after round 6's approval of 59c516a: 83a4dfc, a8a2f54, 8825173 (as entry 27), 6905030 (clean merge of
  origin/HEAD, PR 83), d73140a.
- AC1–AC11 are met by the tests PLAN.md names, as entries 23 and 25 list, except AC2, now
  `test_a_task_id_is_taken_whichever_kind_holds_it` with `test_the_next_task_id_is_one_more_than_the_highest_padded_to_four_digits`,
  and AC6, now without the two removed `ProjectTasks` tests. No human change to TASK.md waits to be folded in.
Next: the reviewer's code round 8 on d73140a.

## 32 · reviewer · approved
Done: code round 8 on d73140a, in REVIEW.md. TASK.md is at ea6b764 and PLAN.md at a53b8d4; both were written by
allowed commits. R20–R26 are closed. In a throwaway clone, the host tier, ruff and mypy pass, and every AC has the
test the round's table names. 2 new Follow-ups (R27, R28), no Blocking finding and no design question. No human
change to TASK.md waits to be folded in, and no question to the architect is open.
- Follow-up: src/foundry/project_tasks.py:278 `_read_task_ids` · its docstring says it returns "the ids of its tasks", but it returns every dir name · a reader who trusts it skips the filter that taken_task_ids (:138) applies.
- Follow-up: src/foundry/project_tasks.py:101 `create_task` · its refusal checks and its write-and-push share one body · the next check added lengthens it further.
- Follow-up: tests/test_project_tasks.py:190 `test_a_new_task_s_turn_is_the_template_s` · a possessive in the name, `_s` · it reads as a plural or a typo.
Next: the dev takes R27 and R28, or leaves them as Follow-ups, opens the pull request and ends with pr-ready.

## 33 · reviewer · changes-needed
Done: after round 8 (entry 32), the human asked in my session for its two Follow-ups to be fixed before the pull
request. That makes this changes-needed, not approved. Round 8's verdict stands for everything else: no Blocking
finding, and R20–R26 closed.
- Answers R27: fix it (the human). PLAN.md's Docs gives the sentence at `src/foundry/project_tasks.py:12-13`, so amend
  it there first. The sentence should say that the write's own checks refuse only a change that clashes with its own
  task, and that its atomic push, never forced, refuses any change to NOTES_BRANCH since the write's own fetch.
- Answers R28: fix it (the human). Remove the overlap between `test_a_task_id_is_taken_whichever_kind_holds_it`
  (`tests/test_project_tasks.py:157-169`) and `:147-154`. Either drop the parametrized test and point AC2 at AC1's
  test, or fold its two-open-dirs case into `:153`. PLAN.md's Tests (AC2) names the test, so amend that line first.
- These plan amendments are approved by the human here, as in entry 29. Mark each line `Amended: R27` or
  `Amended: R28`.
Next: the dev amends PLAN.md for R27 and R28, fixes both, answers each by its id, and ends with ready-for-review for
round 9. Round 9 will review only that fix diff.

## 34 · dev · progress
Done: merged origin/HEAD into task/wcf-0033 (already up to date). Amended PLAN.md for R27 (Docs, the docstring
sentence) and R28 (Tests, AC2), each line `Amended: R<n>`, as the human approved in entry 33. Fixed both in 0163429.
- plan-approved (the human, entry 33) at the PLAN.md commit that follows this entry.
Next: wait for PR 80's CI on 0163429, answer R27 and R28, end with ready-for-review.

## 35 · dev · ready-for-review
Done: round 8's two Follow-ups, which the human asked fixed (entry 33), fixed in 0163429 on PLAN.md as amended in
b31b1cd. Locally ruff (check and format), mypy, vulture, pylint and `uv run pytest --cov` (97.34%) pass; PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/80 is a draft at 0163429 and its CI passes.
- Answers R27: fixed in 0163429. `src/foundry/project_tasks.py:12-14` now says the write's own checks refuse only a
  clash with its own task, and its atomic push, never forced, refuses any change to NOTES_BRANCH since that fetch.
  PLAN.md's Docs has the same sentence (b31b1cd).
- Answers R28: fixed in 0163429. `test_a_task_id_is_taken_whichever_kind_holds_it` is dropped; AC2 now points at
  AC1's `test_taken_task_ids_are_the_open_closed_and_branch_ones_and_reading_them_changes_nothing`, which takes one id
  of each kind, plus AC3's `next_task_id` test and the AC1 CLI test. PLAN.md's Tests (AC2) amended (b31b1cd).
- Commits after round 8's approval of d73140a: 0163429 only.
- AC1–AC11 are met by the tests round 8's table names, except AC2 as above. No human change to TASK.md waits to be
  folded in.
Next: the reviewer's round 9 on the fix diff d73140a...0163429.

## 36 · reviewer · approved
Done: code round 9 on 0163429, the fix diff `d73140a...0163429`, in REVIEW.md. TASK.md is at ea6b764 and PLAN.md
at b31b1cd; both were written by allowed commits. R27 and R28 are closed. In a throwaway clone at 0163429, ruff
(check and format), mypy and `uv run pytest --cov` (97.34%) pass. No new finding, no design question, and no
question to the architect open. No human change to TASK.md waits to be folded in.
Next: the dev opens the pull request (PR 80 out of draft) and ends with pr-ready. R18 stays a Follow-up.
