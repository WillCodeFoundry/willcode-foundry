# Log

## 1 · planner · planned
Done: TASK.md written and approved by the human. Outcome `planned`: the work
adds methods to `ProjectClone` and `ProjectTasks` and a `TaskSummary` value
type, within those modules' stated jobs; no new module, seam, rule or ADR.
Next (dev): start from TASK.md's "Context". Suggested follow-ups, not part of
this task:
- `foundry repo check` prints per-project errors on stdout, inside its report;
  `task list` prints them as `error: ...` on stderr. Consider making `repo
  check` match.
- Git keeps no empty dir, so `.agent/tasks/open/` vanishes when its last task
  closes; `task list` copes by catching a narrow missing-path error. Consider
  a task that keeps the dir in git (e.g. a `.gitkeep` seeded by `create` and
  kept by `close`), after which that catch could go.

## 2 · dev · progress
Done: read TASK.md, the code and the notes; the default branch is already merged.
Next: test-first, one slice per commit: (1) `ProjectClone.fetch_branch`,
`local_list_dir`, `local_read`; (2) `TaskSummary` and
`ProjectTasks.list_open_task_summaries`, plus the fetch count; (3) the pure
listing function and the `task list` parser and `main`; (4) README and
ARCHITECTURE.md. Then the host tier, ruff and mypy, `NAMES.md`, and the draft PR.

## 3 · dev · ready-for-review
Done: all acceptance criteria met, in commits on task/wcf-0028 (clone methods;
`list_open_task_summaries` with the fetch-count test; `task list` and its
pure `listing_lines`; README and ARCHITECTURE.md). Host tier, ruff and mypy
pass, and so does CI on the draft PR https://github.com/WillCodeFoundry/willcode-foundry/pull/43.
No merge conflicts. Names are in NAMES.md.
Next (reviewer): check the symlinked-TURN and upper-case-dir handling. Suggested
follow-ups, not part of this task: none beyond the planner's two.

## 4 · reviewer · changes-needed
Done: round 1 of REVIEW.md, reviewing 1ab21bc against TASK.md at e3b591a (no
other role changed it). pytest, ruff and mypy pass. Every acceptance
criterion is met; three findings block, all local fixes:
- R1: the per-project catch sits in `list_main`, against design rule 7, and no
  test reaches it.
- R6: `list_open_task_summaries` does four jobs, with the id check tangled into
  the loop.
- R7: `listing_lines` splits rows by project, then regroups them.
Next (dev): fix R1, R6 and R7 test-first, and answer each by id. Follow-ups,
fix or defer: R2 (module docstring), R3 (test the exit code and streams,
after R1), R4 (multi-line TURN), R5 (run's fix hint in a listing), R8
(`_local_ref` not used by `read`/`push_atomic`).

## 5 · dev · progress
Done: round 1's findings, in 4195ec5, 87a4ac7, 8e7f8d6 and 294b4af. No merge
was needed (the default branch has no new commits). Host tier, ruff and mypy pass.
- Answers R1: fixed in 4195ec5. The per-project catch is `read_project_listing`
  (renamed in 294b4af), tested over a good and an unreachable project; `list_main`
  only builds, loops and prints.
- Answers R2: fixed in 4195ec5.
- Answers R3: fixed in 4195ec5. A test runs `cli.main(["task", "list"])` in a
  temporary foundry instance (as `test_skills.py` does): the good project on
  stdout, the failed one as `error:` on stderr, exit 1; exit 0 when only the
  good one is named.
- Answers R4: deferred, because ADR 0011 makes `TURN` one line, so only a
  hand-edited `TURN` does this, and the shared `_turn_of` serves `read_task_turn`,
  which TASK.md says not to change. A first-line-only rule would be its own decision.
- Answers R5: fixed in 4195ec5. `_turn_of` keeps the shared first part and takes
  each caller's fix: `read_task_turn` keeps "Name the role to run instead.",
  listing says "Write the next role's name in it."
- Answers R6: fixed in 4195ec5. The id check is `_open_task_in_dir`, the turn read
  `_read_local_task_summary`; the method is now fetch, list, map.
- Answers R7: fixed in 87a4ac7. Widths first, then each project in one pass.
- Answers R8: fixed in 8e7f8d6. `read` and `push_atomic` use `_local_ref`.
Next: wait for CI on PR #43, then end the turn ready-for-review. Follow-up: R4.

## 6 · dev · ready-for-review
Done: every round 1 finding answered (entry 5): R1, R2, R3, R5, R6, R7, R8 fixed
in 4195ec5, 87a4ac7, 8e7f8d6, 294b4af; R4 deferred. All acceptance criteria
still met. Host tier, ruff and mypy pass, and CI passes on 294b4af in the draft
PR https://github.com/WillCodeFoundry/willcode-foundry/pull/43. No merge conflicts.
New names are in NAMES.md (`read_project_listing`, `_read_local_task_summary`,
`_open_task_in_dir`).
Next (reviewer): round 2. Follow-ups, not part of this task: R4 (multi-line
`TURN`), and the planner's two.

## 7 · reviewer · approved
Done: round 2 of REVIEW.md, reviewing 294b4af against TASK.md at e3b591a (unchanged; no other role changed it). pytest (host tier), ruff and mypy pass.
- R1, R2, R3, R5, R6, R7 and R8 are closed. R4 is deferred.
- The fixes raise no new findings.
Next (dev): end with `pr-ready`: mark PR #43 ready for the human. Follow-ups, not part of this task: R4 (multi-line `TURN`), and the planner's two in entry 1.

## 8 · reviewer · changes-needed
Done: added round 3 to REVIEW.md, reviewing 294b4af again. This replaces entry 7's `approved`. After round 2, the human asked for `_open_task_in_dir` to be fixed before the PR. Round 3 has one Blocking finding:
- R9: `_open_task_in_dir` builds the task with `Task.as_open`, which lowercases the dir name. It then compares the id with the dir name again to catch the case it just lowercased. The plain `Task(dir_name, Status.OPEN)` constructor already refuses upper case.
- Also under R9: `Task`'s invalid-id message should say lowercase letters.
Next (dev): fix R9 test-first and answer it by id, then end `ready-for-review`. Note that this is round 3. If the next round finds a Blocking finding still open, the reviewer ends `no-agreement` and the task goes to the human.

## 9 · dev · progress
Done: merged the default branch (#44, role models) into the task branch in
3b6ff1e, cleanly, no conflicts; host tier, ruff and mypy pass.
- Answers R9: fixed in da1c3b8. `_open_task_in_dir` builds `Task(dir_name,
  Status.OPEN)` and only wraps `Task`'s error with the path and the fix; the
  extra comparison and its own reason are gone. `Task`'s message says
  "use lowercase letters", pinned by a new test, and the `WCF-1` listing test
  now pins the whole message.
Next: wait for CI on PR #43, then end ready-for-review.

## 10 · dev · ready-for-review
Done: R9 answered (entry 9), fixed in da1c3b8; the default branch merged
cleanly in 3b6ff1e. All acceptance criteria still met. Host tier, ruff and mypy
pass, and CI passes on da1c3b8 in the draft PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/43. No new names.
Next (reviewer): round 4. Follow-ups, not part of this task: R4 (multi-line
`TURN`), and the planner's two in entry 1.

## 11 · dev · progress
Done: at the human's request, removed the single-caller helper `_open_task_in_dir`,
in 17606fe. `list_open_task_summaries` builds `Task(name, Status.OPEN)` for each dir
in one comprehension under one `try`, before any TURN is read, so the `except`
can't catch a turn error. The message changed shape, since the comprehension's
name isn't in scope in the `except`: "`.agent/tasks/open/ on agent-notes has a
dir that isn't a task id: task id 'Bad Dir' is not valid: .... Rename or remove
the dir.`" Task's error quotes the dir name; both tests pin the new wording.
Host tier, ruff and mypy pass. Recorded in NAMES.md.
Next: wait for CI on PR #43; TURN stays reviewer, for round 4 to review 17606fe too.
