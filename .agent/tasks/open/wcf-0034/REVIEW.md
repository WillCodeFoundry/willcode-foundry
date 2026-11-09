# Review: wcf-0034

## Round 1, plan (reviewing PLAN.md at 24ff9dd)

Reviewed against `TASK.md` at e475e61. That commit is signed by the planner's identity, which the architect shares, so it could equally be the architect's. `PLAN.md` 24ff9dd is signed by the dev. No other role changed either file.

### Standards

Both citations hold. DR6 (`ARCHITECTURE.md:81`): `cli.main` already prints `FoundryError` and `GitError` as `error: <message>` (`src/foundry/cli.py:41-42`), so the plan adds no handling. DR7 (`ARCHITECTURE.md:82`): `show_main` only composes; the logic sits in `show_lines`, `last_log_entry` and `fetch_task_turn_and_log`.

No design trigger is tripped. No module is added or moved, and no design rule or ADR is added or broken. `is_link` only adds a method, `_ls_tree` is private, and step 1 is a test-only move.

The Docs list misses two docstrings:

- **R4 · Follow-up.** `_ls_tree`'s docstring (`src/foundry/project_scratch_clone.py:191`) says it gives "The type and name of each entry". Step 2 makes it return the mode as well. Add it to the Docs list.
- **R5 · Follow-up.** The module docstring of `tests/support/project_repository.py:1-2` lists what the module holds. Step 1 adds a git stand-in without updating it. Add the docstring to the Docs list. It shares a cause with R3 and R6: the AC4 test needs the stand-in's dir, but step 1 says it returns an env.

### Spec

The plan checks out against the code:

- The reused messages match it word for word: `config.py:51`, `task.py:64`, `project_scratch_clone.py:115`, `project_tasks.py:205-211`, `MissingTurnError`, `_read_log`.
- A dir fails as missing.
- A link reads as its target's name today, so `is_link` is needed, and the AC7 test would catch it if missing.
- `Task.as_open` runs before any git.
- No step does anything OS1–OS9 rules out.

- **R1 · Blocking.** AC6 ("fetches `agent-notes` exactly once, as counted by the test suite's counting stand-in for git") is tested only on `ProjectTasks.fetch_task_turn_and_log` (PLAN.md, Tests, AC6).
  - Gap 1: a `show_main` that fetched again would still pass, for example one that also called `fetch_task` or `fetch_task_turn`.
  - Gap 2: AC4's test treats an empty call log under `cli.main` as proof that no git ran. No test shows that this `PATH` setup records anything when git does run, so a stand-in that git never reaches would also pass.
  - Who hits it: any dev who later changes `show_main`.
  - Direction: also count fetches end to end through `cli.main` for a successful `show`, with AC4's `PATH` setup, and check there is no commit or push.
- **R2 · Blocking.** AC8's README sentence ("names `foundry task show`") has neither a test nor a reason. The Docs list makes the edit, and the Tests section covers only `--help` and the command table. `test_the_readme_lists_exactly_the_commands_foundry_defines` reads table rows only. Direction: assert the sentence in `tests/test_docs.py`, or state why no test can show it.
- **R3 · Follow-up.** Step 1 says `counting_git(directory, git_env)` returns an env. The AC4 test prepends "`counting_git`'s dir" to `PATH`. Direction: give the helper one shape that serves both uses. It shares a cause with R5 and R6.

### Behaviour

Not run: a plan round.

### Smells

Not run: a plan round.

### Names

Clean:

- `foundry task show`.
- `is_link`, since "link" is the code's word (`project_scratch_clone.py:42,137`).
- `last_log_entry`.
- `TaskTurnAndLog` (`task`, `turn`, `log`).
- `fetch_task_turn_and_log`.
- `show_main` and `show_lines`.
- The new link error, which mirrors `project_scratch_clone.py:137`.
- The stdout lines `status: closed`, `turn:` and `no log entry yet`.
- The `_ls_tree` change, once R4 is fixed.

Two findings:

- **R6 · Blocking.** `counting_git` leaves the helpers' family word.
  - Its siblings are `scripted_stand_in`, `stand_in` and `recording_stand_in` (`tests/support/machine.py:34,44,75`), and TASK.md calls it "the counting stand-in for git".
  - Read bare, it looks like an instance of the `Git` class (`src/agent_runtime/git.py`).
  - The plan also gives it two return shapes (see R3).
  - Who hits it: the next reader of the AC4 and AC6 tests and of CONTRIBUTING.md's helper table.
  - Direction: name it in the `*_stand_in` family, with one return shape.
- **R7 · Blocking.** `fetch_count(log)` uses `log` for the file of recorded git calls.
  - GLOSSARY.md's **Log** is a task's `LOG.md`, and **Progress** lists "log" under _Avoid_.
  - The AC6 test in `tests/test_project_tasks.py` will hold both kinds of log in one scope: `TaskTurnAndLog.log` and `last_log_entry(log)` sit beside it.
  - The old inline `log` (`tests/test_project_tasks.py:571`) was local. Step 1 spreads it into a shared helper.
  - Direction: name the parameter for git's calls.

### Design questions

None.

Summary: Standards 2 findings, none blocking (worst: R5, a support module docstring left out). Spec 3, of which 2 block (worst: R1, AC6 not shown end to end). Names 2, both blocking (worst: R6, `counting_git` outside the stand-in family with two return shapes). Behaviour and Smells were not run. No design questions are open.

Verdict: plan changes needed

## Round 2, plan (reviewing PLAN.md at 9aa5346)

Reviewed against `TASK.md` at e475e61, unchanged since round 1. That commit is signed by the planner's identity, which the architect shares, so it could equally be the architect's. `PLAN.md` 92170f5 and 9aa5346 are signed by the dev. No other role changed either file. `LOG.md` holds no change to `TASK.md` that the human decided and `TASK.md` lacks. This round reviews the fix diff `24ff9dd..9aa5346` of `PLAN.md`.

### Earlier findings

- **R1: closed.** AC6 is now tested end to end through `cli.main`: one fetch, no `commit` or `push`, and refs unchanged. So a second fetch in `show_main` fails it. Foundry runs a bare `git` (`src/agent_runtime/git.py:102`) in `os.environ` (`src/foundry/commands/task.py:84`), so a stand-in first on `PATH` is reached. AC6 shows the setup records git, which gives AC4's empty record meaning. R9 notes one condition on that.
- **R2: closed.** A new test in `tests/test_docs.py` checks the sentence at `README.md:35`.
- **R3: closed.** `counting_stand_in` has one return shape, the calls file. The caller puts its dir on `PATH`.
- **R4: closed.** `_ls_tree`'s docstring is in the Docs list.
- **R5: closed.** `tests/support/project_repository.py`'s module docstring is in the Docs list.
- **R6: closed.** The helper is now `counting_stand_in(directory, name)` in `tests/support/machine.py`. Its parameters match its siblings' (`tests/support/machine.py:34,44,75`), and it has one return shape.
- **R7: closed.** The function is now `fetch_count(git_calls)`, so "log" stays the glossary's Log (`GLOSSARY.md:73`). "log" is also in the _Avoid_ list at `GLOSSARY.md:129`.

### Standards

- The `tests/support/machine.py` docstring names none of its helpers, so adding one leaves it true.
- `tests/conftest.py` has no module docstring.
- Step 1 is a refactor kept apart from the behaviour change, as git-conventions asks.
- No design trigger: no module is added or moved, and no interface used outside the task changes.
- When the dev edits the stand-ins row (`CONTRIBUTING.md:78`), its Need text should also cover "records its arguments, then runs the real command". That falls within the row edit the plan already names.

- **R8 · Blocking** (raised from Follow-up by the human). Step 1 makes `no_signing_key` a shared fixture by moving it to `tests/conftest.py`. CONTRIBUTING.md's helper table (`CONTRIBUTING.md:76-84`) lists the shared fixtures, and `CONTRIBUTING.md:74` says "A copy of one is a review finding". The Docs list doesn't add the fixture to that table.
  - Who hits it: a later dev who needs git without a signing key reads the table, misses the fixture, and writes their own. This is rare.
  - Direction: add `no_signing_key` to the Docs list's CONTRIBUTING.md entry.

### Spec

Every criterion from AC1 to AC9 has a test at a named seam, and no step does anything OS1–OS9 rules out. The README sentence AC8 names exists (`README.md:35`). The existing inline stand-in (`tests/test_project_tasks.py:574-576`) is a `scripted_stand_in` call plus `which git`, so step 1's move is straightforward.

- **R9 · Blocking** (raised from Follow-up by the human). AC4's empty record proves nothing unless its test sets up `PATH` in the same order as AC6's, and the plan doesn't fix that order (PLAN.md, Tests, AC4).
  - `enter_foundry` calls `set_env(git_env)`, which replaces `PATH` (`tests/conftest.py:146-148`). So a `prepend_to_path` called before `enter_foundry` is silently undone.
  - In AC6 that mistake fails `fetch_count == 1`. In AC4 it passes, because "no record" looks the same as "no git ran". That is R1's gap 2 again.
  - Who hits it: the dev writing the AC4 test, once. The precedent at `tests/test_run.py:125-126` prepends after entering, so the risk is low.
  - Direction: have AC4 and AC6 share one setup, so AC6's proof carries over.

### Behaviour

Not run: a plan round.

### Smells

Not run: a plan round.

### Names

Clean:

- `counting_stand_in`: "counting" comes from AC6.
- Its parameters `directory` and `name`, the same as its siblings'.
- `fetch_count(git_calls)`.
- "calls file" and "the file of recorded calls" in prose. Neither is introduced as a term.
- `no_signing_key`, moved with its name unchanged.
- The stand-ins row edit in the helper table.

No new findings.

### Design questions

None.

Summary: Standards 1 finding, 1 blocking (worst: R8, the newly shared `no_signing_key` missing from the helper table). Spec 1, 1 blocking (worst: R9, AC4's `PATH` setup order not fixed). Names 0. Behaviour and Smells were not run. R1–R7 are closed. No design questions are open.

The human raised R8 and R9 to Blocking after this round first approved the plan at 9aa5346, so that approval is withdrawn.

Verdict: plan changes needed

## Round 3, plan (reviewing PLAN.md at 77c965a)

Reviewed against `TASK.md` at e475e61, which hasn't changed since round 1. That commit is signed by the planner's identity, which the architect shares, so it could equally be the architect's. `PLAN.md` 77c965a is signed by the dev, and no other role changed either file. `LOG.md` holds no change to `TASK.md` that the human decided and `TASK.md` lacks. This round reviews the fix diff `9aa5346..77c965a` of `PLAN.md`.

### Earlier findings

- **R8: closed.** The Docs list adds a row for the `no_signing_key` fixture to CONTRIBUTING.md's helper table, "git with no signing key", worded like the `git_env` row (`CONTRIBUTING.md:82`). It also widens the stand-ins row's Need (`CONTRIBUTING.md:78`) to cover a command that records its arguments, then runs the real one.
- **R9: closed.** AC4 and AC6 now share one fixture, `enter_foundry_counting_git`. It calls `enter_foundry`, then `counting_stand_in`, then `prepend_to_path`, in that order, and the plan says why. The plan's claims match the code:
  - `enter_foundry` returns a callable that replaces the environment with `git_env` (`tests/conftest.py:141-150`).
  - `prepend_to_path` exists (`tests/support/__init__.py:103-105`).
  - `tests/test_run.py:125-126` already uses the same order.
  - `no_signing_key` changes the global config that `git_env` points to, so AC6's use of it still holds after `enter_foundry`.

### Standards

There is no breach.
- CONTRIBUTING.md:72 doesn't stop a test module from having a fixture of its own, and several already do (e.g. `tests/test_run.py:33`). This one has a single user, so it doesn't belong in `tests/support/` or in the helper table.
- It calls the listed helpers instead of copying them (`CONTRIBUTING.md:74`).
- It changes `PATH` only through `ProcessEnvironment`'s existing `prepend_to_path`, so nothing is patched (DR3).
- There is no design trigger.

No new findings.

### Spec

Every criterion still has a test at a named seam in the lines the fix touched. AC4's empty record now means something, because AC6 shows the same setup records git. No step does anything OS1–OS9 rules out. No new findings.

### Behaviour

Not run: this is a plan round.

### Smells

Not run: this is a plan round.

### Names

All clean:
- `enter_foundry_counting_git`, which names its sibling `enter_foundry` and the settled word "counting". It is local to one file, and no other fixture wraps `enter_foundry`.
- "the calls file", which agrees with `git_calls`.
- The helper-table prose ("records its arguments", "the real one", "git with no signing key"), which reuses the table's and the stand-ins' existing words.

No new findings.

### Design questions

None.

Summary: Standards 0 findings, Spec 0, Names 0, and none blocking. Behaviour and Smells were not run. R8 and R9 are closed, and no design questions are open.

Verdict: plan approved at 77c965a
