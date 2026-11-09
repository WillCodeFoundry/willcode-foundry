# Log

## 1 · planner · planned
Done: TASK.md drafted with the human and approved: `foundry task show PROJECT
TASK` prints a task's turn and its LOG.md's last entry (AC1–AC9, OS1–OS9).
It replaces wcf-0030, which the human closed. The human chose to reuse
foundry's existing messages for an unknown project, an invalid id and a task
not found or both open and closed. A malformed task (TURN or LOG.md missing,
not a file or a symlink, or an empty TURN) just fails with an error naming
the task and the file. No follow-ups are recorded on the code this touches.
Next: the dev writes PLAN.md.

## 2 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0034 (already up to date). Wrote PLAN.md:
`foundry task show` reads through a new `ProjectTasks.fetch_task_turn_and_log`
(one fetch), refuses links with a new `FetchedBranch.is_link`, and cuts the
entry with a pure `last_log_entry`. Step 1 moves the counting stand-in for git
into `tests/support/` so AC4 and AC6 reuse it.
Next: the reviewer's plan round; then step 1 of PLAN.md.

## 3 · reviewer · plan-changes
Done: plan round 1 on PLAN.md at 24ff9dd, in REVIEW.md. TASK.md e475e61 (planner's identity, shared with the architect) and PLAN.md 24ff9dd (dev) are signed by allowed identities. No design trigger. Blocking: R1 (AC6 fetch count only at `ProjectTasks`, not end to end; nothing shows AC4's empty call log could see git), R2 (AC8's README sentence has no test or reason), R6 (`counting_git` outside the `*_stand_in` family, two return shapes), R7 (`fetch_count(log)`: "log" is the glossary's LOG.md). Follow-ups: R3, R4, R5.
Next: the dev revises PLAN.md for R1, R2, R6, R7 (and R3–R5 if cheap), answers each in LOG.md, and hands back with plan-ready.
- Follow-up: src/foundry/project_scratch_clone.py:49 `FetchedBranch.read_text` · returns a link's target name as if it were the file's text · every caller must remember to check `is_link` first.
- Follow-up: tests/support/machine.py:77 `recording_stand_in` · its record is named `log` · clashes with the glossary's Log in every test using it.
- Follow-up: src/foundry/project_tasks.py:127 `fetch_task_turn` · returns a `str` beside the `TaskTurn` dataclass · a reader at the call site expects a `TaskTurn`.

## 4 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0034 (already up to date). Revised
PLAN.md for plan round 1, in 92170f5. Checked LOG.md: no human-decided change
waits for TASK.md.
- Answers R1: fixed in 92170f5. AC6 is now tested end to end through
  `cli.main`, with the stand-in on `PATH` as AC4 sets it up: one fetch, no
  commit or push, refs unchanged. That same test shows the setup records git,
  so AC4's empty record means something.
- Answers R2: fixed in 92170f5. A new test in `tests/test_docs.py` checks that
  the README sentence about "the question at the end of its `LOG.md`" names
  `foundry task show`.
- Answers R3: fixed in 92170f5. `counting_stand_in(directory, name)` returns
  only the calls file; the caller puts `directory` on `PATH`.
- Answers R4: fixed in 92170f5. `_ls_tree`'s docstring added to Docs.
- Answers R5: fixed in 92170f5. The module docstring of
  `tests/support/project_repository.py`, which gains `fetch_count`, added to
  Docs; the stand-in itself moves to `tests/support/machine.py`.
- Answers R6: fixed in 92170f5. Renamed `counting_stand_in`, in
  `tests/support/machine.py` beside its siblings, with one return shape.
- Answers R7: fixed in 92170f5. `fetch_count(git_calls)`.
Next: the reviewer's plan round 2; then step 1 of PLAN.md.

## 5 · dev · progress
Done: at the human's question, whether an existing stand-in could serve,
PLAN.md step 1 now says `counting_stand_in` is built on `scripted_stand_in`,
and why `recording_stand_in` doesn't fit. No change of name, seam or approach.
Next: the reviewer's plan round 2; then step 1 of PLAN.md.

## 6 · reviewer · plan-approved
Done: plan round 2 on PLAN.md at 9aa5346, in REVIEW.md. TASK.md e475e61 (planner's identity, shared with the architect) and PLAN.md 92170f5, 9aa5346 (dev) are signed by allowed identities. No human-decided TASK.md change is pending. R1–R7 closed. New follow-ups, neither blocking: R8 (add `no_signing_key` to CONTRIBUTING.md's helper table once it's shared), R9 (AC4 and AC6 share one setup, prepending to `PATH` after `enter_foundry`). No design trigger.
Next: the dev implements PLAN.md from step 1, and picks up R8 and R9 if cheap.
- Follow-up: tests/support/machine.py:77 `recording_stand_in` · names its record file `log` (`{name}.log`), a glossary _Avoid_ word · its sibling `counting_stand_in` will call the same kind of file `git_calls`.
- Follow-up: tests/support/machine.py:89 `TemporaryMachine.passwd_log` · the same "log" for a file of recorded calls · renamed together with the line above.
