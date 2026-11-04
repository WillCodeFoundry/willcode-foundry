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
