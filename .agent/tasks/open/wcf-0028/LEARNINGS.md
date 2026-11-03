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
- 2026-11-03 [decision] — `list_open_task_summaries` refuses an upper-case dir under `open/` as an invalid id: `Task.as_open` lowercases, which would read the wrong `TURN` path and report a misleading "no turn".
- 2026-11-03 [testing] — The fetch count test puts a `git` shim on `PATH` that logs its arguments and execs the real git; `uv sync --group dev` is needed before `uv run pytest`.
- 2026-11-03 [review] — Dropped from round 1 as below the bar: a symlinked
  `.agent/tasks/open` reads as "no open tasks" (nobody would commit one), and
  `ProjectListing`'s `summaries`/`error` pair (the spec asks for an error value).
- 2026-11-03 [testing] — A command's streams and exit code can be tested end to end
  without patching git: write a `config/foundry.yaml` in a temporary folder naming
  real temporary repositories, `monkeypatch.chdir` into it, set the `git_env`
  variables with `monkeypatch.setenv`, and call `cli.main` (precedent:
  `tests/test_skills.py`).
- 2026-11-03 [review] — Round 2 dropped the Names sub-review's "`_with_turn` is a homonym of `_with_commit`": one `_with_` helper is no agreed convention, and the same code prints "with turn ROLE" as a filter. Check a homonym claim against how the codebase's own prose uses the word before letting it block.
- 2026-11-03 [decision] — Superseding the earlier upper-case entry (R9): a dir
  name is never typed, so `_open_task_in_dir` uses the plain `Task(...)`
  constructor, which checks the id as it stands; only `from_id_and_status`/
  `as_open` lowercase, for ids people type.
