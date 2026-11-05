# Log

## 1 · planner · planned
Done: TASK.md written and approved by the human, pushed in f2a97c5.
- The human asked for the next priority task, then chose a command to hand a
  task's turn on, with a LOG.md entry, over the other candidates (wcf-0030's
  PR/CI follow-up, a `.gitkeep` in `.agent/tasks/open/`, `repo check` errors
  on stderr, small cleanups).
- Why `planned`, agreed with the human: one `ProjectTasks` method beside
  `close_task`, one command beside `close`, one constant in `task.py`; no new
  module, seam, rule or ADR.
- The human chose not to wait for wcf-0030. Overlap to watch: wcf-0030 also
  plans `LOG_FILE` in `src/foundry/task.py` and a log-reading module.
  Whichever merges second reuses the other's `LOG_FILE`; swapping this task's
  entry-number helper for wcf-0030's module is a follow-up.
No questions open.
Next (dev): start from TASK.md's "Context". Next (human): tell wcf-0030's
architect about the shared `LOG_FILE`. Suggested follow-ups, not part of this
task: close wcf-0028 (merged as PR #43, notes still open with TURN human).

## 2 · dev · progress
Done: read TASK.md, the notes and the code it names; merged origin/HEAD (up to date).
Next: test-first, one commit per slice, at TASK.md's seams:
1. `LOG_FILE` in `task.py`, with the contract test against `git_hooks.LOG_FILE`.
2. `log_with_turn_entry(log, before, after, note)` in `project_tasks.py`: the new `LOG.md` text, from plain strings.
3. `ProjectTasks.hand_on_turn(task_id, turn, note)` returning a `TurnChange`, against real repositories.
4. In `commands/task.py`: `check_turn_arguments` (role, note, project, task id, before any git), `turn_report`, the `turn` parser and `turn_main`, end to end through `cli.main`.
5. Docs: README table and `TURN` paragraph, ARCHITECTURE codemap, GLOSSARY "Log", `agent-kit/AGENTS.md` sentence.
Then a draft PR, CI, `ready-for-review`.

## 3 · dev · progress
Done: steps 1–3 of entry 2, in 48ffcc6, 889c2a6 and 6e5dc3c: `task.LOG_FILE` (and `Task.log_file`) with the
contract test; `log_with_turn_entry`; `ProjectTasks.hand_on_turn` returning `TurnChange`, tested against real
repositories. Two changes to `ProjectClone` the byte-for-byte criterion needed, each with a test at the
`ProjectTasks` seam: a new `read` of the checked-out file, exact; and `write` replacing a link rather than
writing through it.
Next: step 4, the command in `commands/task.py`.

## 4 · dev · ready-for-review
Done: every acceptance criterion in TASK.md, in 48ffcc6, 889c2a6, 6e5dc3c and 0fdb66d; draft PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/46, CI passing (lint, mypy, host tier on 3.11 and 3.14,
sandbox-image, ci-gate). Merged origin/HEAD at the start and the end: up to date both times, no conflicts.
- [x] `turn` writes `ROLE\n` to `TURN`, appends one entry, one signed commit `Turn of task <id>: <old> → <new>`.
- [x] ROLE, project, task id and `--note` refused by `require_turn_arguments` before any git.
- [x] Refusals: not found / both (from `get_task_by_id`), closed, same turn, no `LOG.md` or not a file (dir or
  link), no signing key; each pushes nothing; end to end shows `error:` on stderr and nothing on stdout.
- [x] `<old>` is `none` for a missing or blank `TURN`; entry format, numbering after the last heading, stdout lines.
- [x] `task.LOG_FILE`, held to `git_hooks.LOG_FILE` in `tests/test_task_contract.py`.
- [x] README table, `TURN` paragraph (and the signing sentence), ARCHITECTURE codemap, GLOSSARY "Log",
  `agent-kit/AGENTS.md`'s `LOG.md` section.
- [x] Host tier, ruff, mypy.
For the reviewer: two changes to `ProjectClone` beyond TASK.md's list, see LEARNINGS.md: a new `read` that keeps
the log byte for byte, and `write` replacing a link instead of writing through it.
Next (reviewer): review PR 46. Suggested follow-ups, not in this task: replace `log_with_turn_entry`'s numbering
with wcf-0030's log module once both merge; `ProjectClone.exists` follows links, so a linked notes dir counts as
a task.

## 5 · dev · ready-for-review
Done: the human asked for the closed-task refusal to name the whole command, as `foundry run` does. Fixed in
f644589. It now says ``task <id> is closed: reopen it with `foundry task reopen <PROJECT> <id>` ``.
- The closed check moved to `hand_on_open_task_turn` in `commands/task.py`, like `run.py`'s
  `require_open_task_and_role`. `ProjectTasks.hand_on_turn` now takes the `Task` that `get_task_by_id` found, so
  `agent-notes` is fetched once. The module docstring names it as an exception to "callers pass task ids".
- The `ProjectTasks` seam's tests go through `hand_on_open_task_turn`, with a real repository, so not-found and
  closed are still checked to push nothing.
CI passes on f644589. The merge of origin/HEAD was up to date.
Next (reviewer): review PR 46.

## 6 · dev · ready-for-review
Done: at the human's call, in 7b35b61, `ProjectClone.read` is dropped and `LOG.md` is read with `fetched_read`.
`ProjectClone.write` now raises a FoundryError on a link (`<path> is a link: foundry writes only files`) instead
of replacing it. The CRLF and invalid-byte test is gone; linked `TURN` and `LOG.md` are refusal cases that push
nothing. See LEARNINGS.md for what "byte for byte" now covers. CI passes on 7b35b61. The merge of origin/HEAD was
up to date.
Next (reviewer): review PR 46.

## 7 · reviewer · design-question
Done: round 1 of REVIEW.md, reviewing 7b35b61 against TASK.md at f2a97c5. That commit is signed by the planner's identity, which the architect shares. No other role changed TASK.md, and the task has no DESIGN.md. The host tier, ruff and mypy pass. Spec: every criterion is met. Findings: 1 Blocking (R10, Names), 1 design question (R3), 8 Follow-ups (R1, R2, R4–R9).
- Asks R3 → architect: `foundry task turn` appends to a task's LOG.md from outside its session. A running role's unpushed LOG.md entry then conflicts on `pull --rebase`, which agent-kit/AGENTS.md says "never conflicts". Should the rule change, should the human be told not to hand on a running task, or should something else be done? See REVIEW.md, round 1.
Next (architect): settle R3 with the human. Next (dev): R10 and the Follow-ups, once R3 is settled.

## 8 · reviewer · design-question
Done: at the human's request, round 1's Names section in REVIEW.md was amended in place, after a check against the names earlier tasks renamed (wcf-0027, wcf-0028). It adds R11 (`role_name` holds a turn), R12 (`_read_fetched_turn_text` beside `_read_fetched_turn`) and R13 (`require_turn_arguments` doesn't name its result), all Blocking, and adds the `report`/`changed` clash to R10. Findings are now 4 Blocking (R10–R13), 1 design question (R3) and 8 Follow-ups. R3's question to the architect in entry 7 still stands.
Next (architect): settle R3 with the human. Next (dev): R10–R13 and the Follow-ups, once R3 is settled.

## 9 · architect · designed
Done: DESIGN.md written with the human and approved, pushed in 9b086e2. Its one decision answers R3.
- Answers R3: DESIGN.md changed in 9b086e2: `foundry task turn` is for a task whose role isn't running. The
  README's `TURN` paragraph says so in one sentence, and nothing checks it. `agent-kit/AGENTS.md`'s "never
  conflicts" rule stays. The human chose this over a recovery procedure in AGENTS.md, a running-sandbox check
  and a `merge=union` attribute, as the simplest.
No questions open.
Next (dev): the README sentence from DESIGN.md, then R10–R13 and the Follow-ups.

## 10 · dev · ready-for-review
Done: DESIGN.md's README sentence, and round 1's findings, in 21e59a9, bf18d7a and 62665d2. CI passes on 62665d2.
The merge of origin/HEAD was up to date at the start and the end. Renames are recorded in NAMES.md.
- DESIGN.md: README now says to hand a task on only while its role isn't running, in 21e59a9.
- Answers R1: fixed in 62665d2. The precondition and its reason are now separate sentences.
- Answers R2: fixed in 21e59a9. The hand-on sentences are split into their own short paragraphs.
- Answers R3: settled by DESIGN.md (entry 9); README sentence in 21e59a9.
- Answers R4: deferred, because TASK.md fixes `<old>` as TURN's stripped text. Both directions depart from that:
  reading a multi-line TURN as `none`, or refusing it. That is the planner's to decide.
- Answers R5: fixed in 62665d2. `_commit_and_push` is used by `hand_on_turn` and `_move`.
- Answers R6: fixed in 62665d2. `_read_fetched_log` sits beside `_read_fetched_turn`.
- Answers R7: deferred, because the review's direction is to accept it as is (entry 5's choice).
- Answers R8: deferred, because the direction is to share the helper when either listing next changes.
- Answers R9: deferred, because the review's direction is to accept it as is.
- Answers R10: fixed in bf18d7a. `change` is now `turn_change`.
- Answers R11: fixed in bf18d7a. `role_name` is now `turn`, including the parser dest; the metavar stays `ROLE`.
- Answers R12: fixed in bf18d7a. `_read_fetched_turn_text` is now `_read_fetched_turn_or_empty`.
- Answers R13: fixed in bf18d7a. `require_turn_arguments` is now `require_project_and_turn_arguments`.
Next (reviewer): round 2 on PR 46. Suggested follow-ups, not in this task: R4 (multi-line TURN), R8 (one
known-roles helper), `commands/repo.py`'s `change` for a `RulesetChange` (R10's older drift), and the earlier
ones in entry 4.

## 11 · dev · progress
Done: the human reviewed the code with me after entry 10, and decided these simplifications, to be made in PR 46.
- "Handoff" is the word for changing a task's turn. `hand_on_turn` becomes `ProjectTasks.handoff`, the report
  `handoff_lines`, and the argument check `require_valid_handoff_args`, which returns nothing. GLOSSARY gains
  "Handoff". The command stays `foundry task turn` and the entry heading `human · turn`, as TASK.md fixes them.
- `ProjectTasks` is built from the `Project`, so it knows the project's name. `handoff` takes a task id and
  refuses a closed task itself, as `close_task` does. `hand_on_open_task_turn` and the `assert` go.
- `TurnChange` goes. `handoff` returns the turn before.
- One TURN reader: `_read_fetched_turn` raises `NoTurnError` for a missing or blank TURN, and its `fix`
  parameter goes. `foundry run` and `foundry task list` then give one message, which says to hand the task off
  with `foundry task turn`. This overrides TASK.md's out-of-scope line on `read_task_turn` and
  `list_open_task_summaries` (the human).
- `run.py` spells `LOG.md` as `task.LOG_FILE`. The link refusal is tested on `ProjectClone`, plus one case
  through `handoff`.
Next: make these in small commits, then CI, then `ready-for-review`. Mocks for external components come after.

## 12 · dev · progress
Done: entry 11's simplifications, in a49fc8c, a9a3bf5, ff8b2d9, 6863efb and ec3e9b7. CI passes on ec3e9b7;
origin/HEAD merged, up to date. The diff since 62665d2 is 132 lines added, 153 removed.
- `ProjectTasks` is built from the `Project` (a49fc8c); `run.py` and `test_run.py` change with it.
- `ProjectTasks.handoff(task_id, turn, note=)` refuses a closed task itself and returns the turn before.
  `hand_on_open_task_turn`, `TurnChange` and the `assert` are gone. `require_valid_handoff_args` returns nothing;
  `turn_main` looks the project up, and the end-to-end test now checks an unknown project (a9a3bf5).
- `NoTurnError` and one reader; `run` and `list` say to hand the task off with `foundry task turn` (ff8b2d9).
- The link refusal is tested on `ProjectClone.write`; `run.py` uses `LOG_FILE` (6863efb).
- "Handoff" in the docs, help text and GLOSSARY (ec3e9b7). Names recorded in NAMES.md.
Note for the reviewer: two of these change behaviour outside TASK.md, at the human's call (entry 11). The
"has no turn" message of `foundry run` and `task list` changed, and ProjectTasks' constructor changed.
Next: the human wants to discuss allowing mocks for external components in tests. Then `ready-for-review`.

## 13 · dev · progress
Done: two more decisions by the human, to be made in PR 46.
- "Byte for byte" is relaxed: the log's entries keep their text, but trailing whitespace at its end and line
  endings may change. The entry follows after one blank line, and the file ends with a newline. This overrides
  TASK.md's criterion (the human).
- The tests in `tests/test_task.py` move onto one `project_repository` fixture (a `ProjectRepository`: the GitHub
  repository behind a project, as a bare repository), in place of the `(origin_dir, git_env, …)` helpers. That
  includes tests from earlier tasks (the human). Fixtures used by one module stay in it; only shared ones go in
  conftest, and no shared test module is added.
Next: the relaxed rule, then the fixture, each its own commit. Suggested follow-up: split `tests/test_task.py`
by module, in a PR of its own.

## 14 · dev · ready-for-review
Done: entry 13's decisions, and the split the human then asked for in this PR. Commits 9a88578, 658ae1d and
0d77ef7. CI passes on 0d77ef7, and origin/HEAD merged up to date.
- 9a88578: `log_with_turn_entry` keeps the log but for its trailing whitespace; a blank log gets no blank line.
  The byte-level checks go.
- 658ae1d: the tests use one `project_repository` fixture, plus `no_signing_key`. No test changes what it checks.
- 0d77ef7: `tests/test_task.py` is split into `test_task.py`, `test_project_clone.py`, `test_project_tasks.py`
  and `test_task_command.py`. All 171 tests kept. `git_env` and `project_repository` go in conftest, since
  several modules use them; everything else stays in its module.
Note for the reviewer: since round 1, the human decided these changes in session, beyond TASK.md and round 1's
findings (entries 11 and 13): handoff naming, `ProjectTasks` built from the `Project`, one "has no turn"
message, the relaxed log rule, the fixture and the split. Round 2 should review 62665d2..0d77ef7 against those
entries. Entry 10's answers to R1–R13 still stand, with names since changed again (NAMES.md).
Next (reviewer): round 2 on PR 46. Suggested follow-ups: R4 (a TURN with more than one line), R8 (one
known-roles helper), `commands/repo.py`'s `change`, and `test_run.py`'s own origin setup, which could move to
`project_repository`.

## 15 · dev · progress
Done: at the human's request, in f5715ef and 703df1d.
- f5715ef: `create` takes a `ProjectTasks`; the `turn_of` and `handoff` wrappers go, so no test imports from
  conftest.
- 703df1d: corrects entry 13's "no shared test module". CONTRIBUTING.md:42 says shared helpers go in
  `tests/support/` and conftests hold only fixtures, and the human chose to follow it. `ProjectRepository`, the
  signer and the git helpers moved to `tests/support/project_repository.py`; the helpers repeated in the test
  modules are imported from it. 171 tests, as before.
Next: CI on 703df1d. The human wants to discuss next how this workflow should handle changes to TASK.md, and a
per-task decision record. TURN stays reviewer.

## 16 · dev · progress
Done: at the human's call, "handoff" names the act wherever "turn" did, in 8aee1ea. The command is
`foundry task handoff`, the log entry is headed `human · handoff`, the commit says `Handoff of task <id>: <old> →
<new>` and stdout says `handoff <old> → <new>`. `log_with_turn_entry` is `log_with_handoff_entry`, and
`TURN_CONFIG` is `HANDOFF_CONFIG`. TURN, the `turn` argument, `NoTurnError` and the `Turn:` line keep "turn": they
name the state. README, GLOSSARY and agent-kit/AGENTS.md follow. The human had me amend TASK.md in place to match,
this once: the title, Goal, criteria, out of scope, Context, seams and terms. ADR 0011's "hand-off" is left as
written. Checks pass; origin/HEAD merged, up to date.
Next: CI on 8aee1ea, then `ready-for-review`.

## 17 · dev · progress
Done: at the human's call, `NoTurnError` is `MissingTurnFileError`, in a35ebbc. It is also raised
for a TURN that is a dir or holds only blanks, as its docstring says; the message is unchanged. Checks pass.
Next: CI, then `ready-for-review`.

## 18 · dev · progress
Done: at the human's call, `MissingTurnFileError` is `MissingTurnError`, in ec90be4: the error covers a TURN
that is missing, a dir or blank, and in each case the task has no turn. Checks pass.
Next: CI, then `ready-for-review`.

## 19 · dev · progress
Done: at the human's call, `_NO_TURN` goes, in f4e16f3: `handoff` writes `"none"` in its `except MissingTurnError`
branch, the only place it is used. Checks pass.
Next: CI, then `ready-for-review`.

## 20 · dev · progress
Done: at the human's call, `handoff` no longer reads or returns the turn before, in 04a60a8. It reads TURN only to
refuse handing a task to the turn it has, under `suppress(MissingTurnError)`. The entry says `Turn: <ROLE>.`,
the commit `Handoff of task <id> to <ROLE>`, stdout `task <id> in <PROJECT>: handoff to <ROLE>`. This removes
the `"none"` stand-in, which a role named `none` would have matched: config accepts any role name. The log's
earlier entries say who had the turn. README's list of signing commands now names `handoff`, missed in 8aee1ea.
TASK.md amended in place, as the human allowed: the Goal, the commit message, the `<old>` criterion (now: a task
with no turn is not refused), the entry format and stdout. Checks pass, and CI passes on 04a60a8.
Next: `ready-for-review`.

## 21 · dev · ready-for-review
Done: TASK.md's log criterion amended in place, as the human allowed: the existing text is kept but for the
whitespace at the file's end and its line endings, as entry 13 decided and `log_with_handoff_entry` does. No code
change. CI passes on 04a60a8; origin/HEAD merged, up to date. PR: https://github.com/WillCodeFoundry/willcode-foundry/pull/46
Note for the reviewer: round 2 covers 62665d2..04a60a8. TASK.md was amended in place this session at the human's
call (entries 16, 20, 21): the command is `foundry task handoff`, the entry heading `human · handoff`, the old turn
is dropped from the entry, commit and stdout, and "byte for byte" is relaxed. The other decisions beyond TASK.md
are in entries 11, 13 and 15.
Next (reviewer): round 2. Follow-ups still listed: R4 (a multi-line TURN), R8 (a shared known-roles helper).
