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

## Round 4 (reviewing ec3810a)

Reviewed against `TASK.md` at e475e61, which is signed by the planner's identity. The architect shares that identity, so the commit could equally be the architect's. `PLAN.md` was approved at 77c965a and is unchanged since. It is signed by the dev. No other role changed either file. `LOG.md` holds no change to `TASK.md` that the human decided and `TASK.md` lacks. This is the first code round, so it reviews the whole diff `9e047ab...ec3810a` (commits d3e2b03, b4145bc, 69c69f5, 647fba9, ec3810a).

### Earlier findings

R1–R9 were closed in the plan rounds. No finding is open.

### Standards

- **R10 · Follow-up · `src/foundry/commands/task.py:131`.**
  - `show_main` calls `task.Task.as_open(args.task_id)` itself, with a comment saying it refuses an invalid id.
  - `handoff_main` instead calls this through `require_valid_handoff_args` (`:121`, `:177`), a function the tests call. So `show_main` is the one composition root whose body names a check (DR7).
  - Reviewer's note: the reviewer downgraded this from Blocking.
    - The check itself lives in `Task.as_open`, which the tests call, and `main` only calls it.
    - The end-to-end AC4 test reaches the line.
    - The approved PLAN.md chose this placement.
    - Nobody is led into a wrong action.
  - Who hits it: a dev who copies the newest command, now and then.
  - Fix: optionally, move the call into a small `require_…` check beside handoff's. Otherwise accept as is.
- **R11 · Follow-up · `src/foundry/project_tasks.py:156-157`.**
  - The new link error chains the fault, the reason and the location behind "and" and a colon, against AGENTS.md "Writing" ("Give each reason its own sentence").
  - It copies `ProjectScratchClone.write`'s existing message, and PLAN.md gives this exact text.
  - Who hits it: a user whose `TURN` or `LOG.md` is a link. That is rare.
  - Fix: accept as is. Rewording means a plan change, and the same rewording for `write`.

Docstrings and docs: nothing the change made untrue. The module docstrings were checked, as were the class docstrings in `project_scratch_clone.py` and `project_tasks.py`, ARCHITECTURE.md's codemap rows, CONTRIBUTING.md's helper table, the README's table and its `LOG.md` sentence, and GLOSSARY.md's Log and Fetched branch.

### Spec

AC1–AC9 are all met in behaviour. The Spec reviewer ran every CONTRIBUTING.md check in a throwaway clone: `pytest --cov` 97.29%, ruff, format, mypy, vulture, pylint 10.00, and shellcheck.

| AC | Code | Test |
|---|---|---|
| AC1 | `last_log_entry`, `fetch_task_turn_and_log`, `show_main`, `show_lines` | `test_the_last_log_entry_…`, `test_show_prints_…[open]` (exact stdout, empty stderr, exit 0) |
| AC2 | `show_lines`' status line | `test_show_lines_…[closed]`, `test_show_prints_…[closed]` |
| AC3 | `show_lines`' fallback | `[template]`, `[no-entry]` |
| AC4 | `task.py:130-131`, before the scratch clone | `test_show_refuses_…_before_running_git` |
| AC5 | existing errors, and the link check | `test_a_malformed_task_s_…` (7), `test_show_fails_…` (10). See R12 |
| AC6 | one `fetch_branch` | `test_show_only_reads_with_one_fetch` |
| AC7 | `is_link` before any read | `[turn-link]`, `[log-link]`, `test_is_link_is_true_for_a_link_only` |
| AC8 | parser help, README | `test_task_help_lists_show`, the two README tests in `test_docs.py` |
| AC9 | | all checks pass |

- **R12 · Blocking · `tests/test_task_command.py:471-482`.**
  - The end-to-end failure test has no case for a `TURN` that is a dir. PLAN.md's AC5 test says "End to end, parametrized over every AC5 failure", and LOG.md entry 11 claims "(all ten failures)".
  - AC5 names eleven failures. The `TURN` cases are missing, not a file, a link, or empty.
  - A `TURN` that is a dir is tested only at `ProjectTasks` (`test_a_malformed_task_s_…[turn-dir]`). `LOG.md` as a dir is tested end to end (`log-dir`).
  - No user would see wrong behaviour, but the tests depart from the approved plan, and the claim overstates the coverage.
  - Fix: add a `turn-dir` case to that list.

### Behaviour

No findings. The Behaviour reviewer ran the suite in a throwaway clone, plus cases of its own:
- CRLF and trailing tabs or blanks in `LOG.md` and `TURN`;
- a `LOG.md` that isn't UTF-8 and has no final newline;
- a heading-like line in a code block, a risk TASK.md accepts;
- a `TURN` with spaces around it, and a `TURN` that is a dir;
- `is_link` on the paths it meets;
- cleanup of the scratch clone on failure;
- nothing on stderr on success.

Each behaved as TASK.md asks. `rstrip()` (`project_tasks.py:295`) also drops trailing tabs and CRs, not only spaces. Accept as is: the output is the same in practice.

### Smells

Functions added or changed:

| Function | Verdict |
|---|---|
| `commands/task.py`: `add_parser` | clean |
| `commands/task.py`: `show_main`, `show_lines` | new, clean |
| `project_scratch_clone.py`: `subdir_names`, `read_text` | clean |
| `project_scratch_clone.py`: `is_link` | new, R13 |
| `project_scratch_clone.py`: `_require_entry`, `_ls_tree` | R13 |
| `project_tasks.py`: `TaskTurnAndLog` | new, clean. It repeats `TaskTurn`'s fields, as the plan names it |
| `project_tasks.py`: `fetch_task_turn_and_log` | new, R15 |
| `project_tasks.py`: `last_log_entry` | new, clean |
| `machine.py`: `counting_stand_in` | new, clean |
| `project_repository.py`: `fetch_count` | new, clean |
| `conftest.py`: `no_signing_key` | moved, clean |
| `test_listing_costs_one_fetch_however_many_tasks` | clean, and simpler than before |
| `enter_foundry_counting_git` | new, clean |
| `store_foundry` | new, R16 |
| `test_show_fails_…` | new, R14, R16 |
| The other new tests in `test_project_scratch_clone.py`, `test_project_tasks.py`, `test_task_command.py` and `test_docs.py` | clean |

- **R13 · Blocking · `src/foundry/project_scratch_clone.py:60-63` and `:71-73`.** Possible copying instead of the seam (python-smells #6).
  - `is_link` repeats `_require_entry`'s `ls-tree` lookup of one path.
  - Widening `_ls_tree` to three fields made `_require_entry` rebuild a list of pairs just to keep its membership test (`:73`), so the change left it more tangled.
  - Who hits it: the next dev who adds an entry check, who would copy the lookup a third time.
  - Fix: one private lookup of the entry at `path` that both use. It is local, and `is_link`'s interface stays as PLAN.md gives it.
  - Shares a cause with R17.
- **R14 · Follow-up · `tests/test_task_command.py:511`.** Possible test that proves nothing (#10).
  - The `hostname`/`MARKER`/`marker` assertion can't fail on its own: `:509` fixes stdout as empty, and `:510` fixes the whole of stderr.
  - Reviewer's note: the reviewer downgraded this from Blocking. AC7 is still shown by `:509-510`, so nobody is misled about what is proven.
  - Fix: drop it, or leave it as is.
- **R15 · Follow-up · `src/foundry/project_tasks.py:153-158`.** Possible half-guard (#4.2).
  - "foundry reads only files" is enforced for `show` only.
  - `_read_turn` and `_read_log` still read a link as its target's name for `fetch_task_turn`, `hand_off` and listing.
  - This is acceptable for now: PLAN.md puts the check here, and OS6 keeps listing as it is.
- **R16 · Follow-up · `tests/test_task_command.py:499-504`.** Possible near-twin (#6).
  - The failure test rebuilds `store_foundry` (`:375-378`) by hand, with `bare` added.
  - Fix: let `store_foundry` include `bare`.
- **R17 · Follow-up · `src/foundry/project_scratch_clone.py:60-73`.** Possible hidden cost (#9).
  - `show` runs `ls-tree` twice per file, once in `is_link` and once in `_require_entry`.
  - R13's fix removes this. On its own, accept as is. Shares a cause with R13.

### Names

No findings. Every name the diff adds matches PLAN.md's Names and Errors and the glossary's words:
- `foundry task show`, `is_link`, `_LINK_MODE`, `fetch_task_turn_and_log`, `TaskTurnAndLog`, `last_log_entry`, `show_main`, `show_lines`;
- `counting_stand_in`, `fetch_count`, `enter_foundry_counting_git`, `store_foundry`;
- the test constants and locals, the link error, and the help and docs prose.

The behaviour of `_ls_tree` and `read_text` changes, and their docstrings and every caller were updated to match. None of the added prose uses a word the glossary says to avoid.

### Design questions

None.

Summary:
- Standards: 2 findings, 0 blocking. The worst is R10, a check named in `show_main`.
- Spec: 1 finding, 1 blocking. R12: no end-to-end case for a `TURN` that is a dir.
- Behaviour: 0 findings.
- Smells: 5 findings, 1 blocking. R13: `is_link` copies `_require_entry`'s lookup.
- Names: 0 findings.
- No design question is open.

Verdict: changes needed
