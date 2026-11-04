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
