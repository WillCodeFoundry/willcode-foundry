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

## 7 · reviewer · plan-changes
Done: at the human's direction, R8 and R9 are now Blocking. Round 2 in REVIEW.md is amended to match, and its verdict is now `plan changes needed`. Entry 6's approval of 9aa5346 is withdrawn.
Next: the dev revises PLAN.md: add `no_signing_key` to the Docs list's CONTRIBUTING.md helper-table entry (R8); have the AC4 and AC6 tests share one setup that prepends the stand-in's dir to `PATH` after `enter_foundry` (R9). Answer each in LOG.md, then hand back with plan-ready.

## 8 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0034 (already up to date). Revised
PLAN.md for plan round 2's R8 and R9. Checked LOG.md: no human-decided change
waits for TASK.md.
- Answers R8: fixed in PLAN.md (this entry's commit). Docs adds a row for the
  `no_signing_key` fixture to CONTRIBUTING.md's helper table, and the stand-ins
  row's Need covers recording then running the real command.
- Answers R9: fixed in PLAN.md (this entry's commit). AC4 and AC6 share one
  fixture in `tests/test_task_command.py`, `enter_foundry_counting_git`, which
  enters the foundry, then prepends the counting stand-in's dir to `PATH`, and
  returns the calls file. New test-only name, listed under Names.
Next: the reviewer's plan round 3; then step 1 of PLAN.md.

## 9 · reviewer · plan-approved
Done: plan round 3 on PLAN.md at 77c965a, in REVIEW.md. TASK.md e475e61 is signed by the planner's identity, which the architect shares. PLAN.md 77c965a is signed by the dev. Both identities are allowed. No change to TASK.md that the human decided is pending. R8 and R9 are closed, there are no new findings, and there is no design trigger.
Next: the dev implements PLAN.md from step 1.

## 10 · dev · progress
Done: merged origin/HEAD into task/wcf-0034 (already up to date). PLAN.md
step 1 in d3e2b03 (`counting_stand_in`, `fetch_count`, `no_signing_key` shared,
CONTRIBUTING.md's helper table) and step 2 in b4145bc (`FetchedBranch.is_link`).
Next: step 3, `last_log_entry` and `ProjectTasks.fetch_task_turn_and_log`.

## 11 · dev · ready-for-review
Done: PLAN.md steps 3–5, in 69c69f5 (`last_log_entry`, `TaskTurnAndLog`,
`ProjectTasks.fetch_task_turn_and_log`), 647fba9 (`foundry task show`,
`show_main`, `show_lines`) and ec3810a (README,
ARCHITECTURE.md, test_docs). Draft PR:
https://github.com/WillCodeFoundry/willcode-foundry/pull/81, CI passes (lint,
mypy, test 3.11/3.14, sandbox-image, ci-gate). Checked LOG.md: no
human-decided change waits for TASK.md. No merge conflicts.
- AC1: `test_the_last_log_entry_runs_from_the_last_heading_to_the_end_without_trailing_blanks`,
  `test_a_task_s_turn_and_log_are_read_from_its_task_notes_dir`,
  `test_show_lines_…[open]`, `test_show_prints_the_turn_and_the_last_log_entry_and_exits_0[open]`.
- AC2: `test_show_lines_…[closed]`, `test_show_prints_…[closed]`.
- AC3: `test_the_last_log_entry_…[template]`, `test_show_lines_…[no-entry]`, `test_show_prints_…[no-entry]`.
- AC4: `test_show_refuses_an_unknown_project_or_an_invalid_id_before_running_git`.
- AC5: `test_a_malformed_task_s_turn_and_log_are_refused_naming_the_task_and_the_file`,
  `test_show_fails_with_one_error_on_stderr_nothing_on_stdout_and_exits_1` (all ten failures).
- AC6: `test_show_only_reads_with_one_fetch` (no_signing_key, one fetch, no commit or push, refs unchanged).
- AC7: `test_show_fails_…[turn-link]` and `[log-link]`; `test_is_link_is_true_for_a_link_only`.
- AC8: `test_task_help_lists_show`, `test_the_readme_lists_exactly_the_commands_foundry_defines`,
  `test_the_readme_names_the_command_that_shows_the_question_a_task_waits_on`.
- AC9: ruff, format, mypy, vulture, pylint, shellcheck and `pytest --cov` (97.29%) pass locally.
Next: the reviewer's code round.

## 12 · reviewer · changes-needed
Done: code round 4 on ec3810a, in REVIEW.md, against TASK.md e475e61 (signed by the planner's identity, which the architect shares) and PLAN.md 77c965a (signed by the dev). No change to TASK.md that the human decided is pending, and no design question is open. All of AC1–AC9 are met in behaviour, and every CONTRIBUTING.md check passes. Blocking: R12 and R13. Follow-ups: R10, R11, R14, R15, R16, R17.
Next: the dev fixes R12 (add a `turn-dir` case to `test_show_fails_…`) and R13 (one private `ls-tree` lookup of a path, shared by `is_link` and `_require_entry`), test-first. The dev answers each finding in LOG.md, then hands back with ready-for-review. R14 and R16 are cheap to take along.
- Follow-up: src/foundry/project_tasks.py:257 `_read_turn`, :271 `_read_log` · read a link as its target's name on every path but `show` (FetchedBranch.read_text's contract) · `foundry run` and `handoff` silently take a linked TURN's target name as the turn.
- Follow-up: tests/support/machine.py:76 `recording_stand_in` · returns `(command, record file)` while its sibling `counting_stand_in` returns only the record file · each caller has to check which shape it has.

## 13 · dev · ready-for-review
Done: merged origin/HEAD into task/wcf-0034 (already up to date). Answered
round 4. CI on PR #81 passes at 2bc81e0 (lint, mypy, test 3.11/3.14,
sandbox-image, ci-gate). Checked LOG.md: no human-decided change waits for
TASK.md. No merge conflicts.
- Answers R12: fixed in 1b80771. `test_show_fails_…` has a `turn-dir` case,
  so it now runs all eleven AC5 failures end to end.
- Answers R13: fixed in 0b3bc58. One private `FetchedBranch._entry(path)`, the
  mode and type at `path` or None, serves `is_link` and `_require_entry`.
- Answers R14: fixed in 2bc81e0. The assertion is dropped.
- Answers R16: fixed in 2bc81e0. `store_foundry` takes `git_env` and includes
  `bare`; the failure test uses it, and the unknown-project message now lists
  `bare, gone, store`.
- Answers R10: deferred, because the check lives in `Task.as_open`, which
  tests call, and PLAN.md places the call in `show_main`; the reviewer accepts
  it as is.
- Answers R11: deferred, because PLAN.md gives this exact text, copied from
  `ProjectScratchClone.write`; rewording both is a plan change for a later task.
- Answers R15: deferred, because OS6 keeps listing as it is, and refusing links
  for `run` and `handoff` is outside TASK.md. Already a Follow-up in entry 12.
- Answers R17: deferred, because R13's fix shares the lookup's code, not its
  call: `show` still runs `ls-tree` once in `is_link` and once in `read_text`
  per file. Removing that means a read that refuses links, which PLAN.md's
  approach turned down. The cost is two local `ls-tree` runs, no network.
- AC1–AC9: as entry 11 lists, with `test_show_fails_…[turn-dir]` added for AC5.
  ruff, format, mypy, vulture, pylint, shellcheck and `pytest --cov` (97.30%)
  pass locally.
Next: the reviewer's code round 5.
