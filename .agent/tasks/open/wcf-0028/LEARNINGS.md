# Learnings

- 2026-11-03 [decision] — `task list` reads each project through one fetch
  and local git-object reads (`fetch_branch`, `local_list_dir`, `local_read`),
  not `read_task_turn` in a loop (which fetches per call) and not the checked-out
  files (the notes branch is agent-written, so a symlinked `TURN` must not be
  followed). Rejected: a pinned-snapshot type (new interface), an eager fetch in
  `in_scratch_clone` (shared with `create`, which may find no `agent-notes`).
- 2026-11-03 [decision] — A missing `agent-notes` branch and a missing or empty
  `TURN` are project failures (rule 6), not "no tasks" or `(none)`. A missing
  `.agent/tasks/open/` is not: git drops empty dirs, so it means no open tasks.
  Rejected: `.gitkeep` (changes `create` and `close`, needs a migration), and
  `local_exists` (a second call for what a narrow exception answers in one).
- 2026-11-03 [decision] — Per-project errors go to stderr as `error: PROJECT: ...`,
  as `cli.main` prints raised errors; `repo check` prints them on stdout, an
  inconsistency left for a follow-up.
- 2026-11-03 [decision] — Type named `TaskSummary`: `TaskTurn` was rejected,
  `TaskAssignment` implies a standing owner, `TaskStatus` clashes with the
  open/closed `Status`.
