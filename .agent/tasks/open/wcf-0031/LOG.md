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
