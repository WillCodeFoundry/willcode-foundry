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
