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
