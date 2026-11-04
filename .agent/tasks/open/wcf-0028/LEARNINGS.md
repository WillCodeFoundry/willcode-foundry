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
- 2026-11-03 [review] — A fix can make an untouched comment wrong: R9 added a direct-constructor caller, which made `_TASK_ID`'s "Matched after lowercasing" comment stale (R10). When a fix changes who calls a function, read the comments on what it calls, not only the lines in the fix diff.
- 2026-11-03 [decision] — Deferred R10 (a stale comment) rather than fix it after
  `Verdict: approved`: any own commit after approval sends the task back to
  review, so an optional comment fix there costs a whole round.
- 2026-11-04 [decision] — R15: `read_task_turn` can use the no-network
  `fetched_read` because `get_task_by_id` either fetched `agent-notes` (through
  `check_out`) or raised `TaskNotFoundError`; there is no path where a task is
  found on an unfetched branch. Kept the "has no TURN, or it is empty" wording for
  a dir at `TURN` too, rather than churning the pinned message.
- 2026-11-04 [tools] — SSH to GitHub failed intermittently with "Permission
  denied (publickey)" on fetches (including a partial clone's lazy blob fetch),
  while `ssh -T git@github.com` and pushes worked; plain retries kept failing,
  then a fetch from the code checkout (which shares the notes checkout's `.git`)
  succeeded and the notes pull after it did too. A push also failed once with
  GitHub's "fatal error in commit_refs" / 500, and succeeded on retry.
- 2026-11-04 [testing] — A check script that runs `uv run pytest | tail` under
  `set -e` passes when pytest fails: the pipeline's status is `tail`'s. Use
  `set -o pipefail`. CI caught the one failure this hid (c6876a8).
- 2026-11-04 [decision] — `ProjectFailure` split from `ProjectListing` (D1): a
  project is listed whole or not at all, so the type should not allow tasks and
  an error together. `repo_policy.ProjectCheck` keeps `error` beside its results
  because a partial check is meaningful there; not a precedent for listing.
- 2026-11-04 [review] — Round 6: the Spec axis found two test gaps by narrowing a line and rerunning the tests (narrowing `except (FoundryError, GitError)` to `except GitError`; counting every project's name in the width). Changes like these find gaps that reading for "a test names this" misses.
- 2026-11-04 [proposal] — reviewer ROLE.md: `no-agreement` fires on any Blocking finding open after round 3, even when the dev and the reviewer don't disagree, as in round 6 here. Either name an outcome for "Blocking, undisputed, past round 3", or let the human raise the round limit for a task.
- 2026-11-04 [testing] — When checking that a test catches a mutation, don't undo
  the mutation with `git checkout <file>` if the file also has uncommitted edits:
  it drops them too. Commit first, or copy the file aside and restore the copy.
- 2026-11-04 [review] — Round 7: for a fix round that only adds tests, the Spec axis closed each finding by redoing the mutation the earlier round named and checking that a test now fails. A finding written with its mutation makes the next round's check mechanical.
- 2026-11-04 [decision] — At `pr-ready`, write the PR body fresh from the `pr` skill rather than patching the draft's body: the patched one kept an oversized Summary (a full call tree), test names with no output as Evidence, and follow-ups under Blast Radius, and the human had to ask for a rewrite.
