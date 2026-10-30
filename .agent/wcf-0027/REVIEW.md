# Review: wcf-0027

The owner asked for a fresh review, so this file was rewritten from scratch. The earlier rounds are in the notes branch's history, and finding ids start again at R1.

This round follows the **proposed** form of the review, at the owner's request (see the `[proposal]` entries in LEARNINGS.md):
- There is a fourth reviewer, **Smells**, which returns a coverage table.
- A smell the diff introduces blocks when its fix is local.
- A finding whose fix would change a DESIGN.md decision is a **design question**, for the owner and the architect.

At the owner's request, findings state the problem and the evidence only, with no fixes. Fixes are for the architect (design questions) and the dev (everything else) to work out.

## Round 1 (reviewing 2585b62)

### Who reads what

| Role | Read | Then |
|---|---|---|
| **Architect** | "Design questions" (R1, R13), then the findings in "Waits for the design" | Update DESIGN.md, or say the design stands. The axis sections are background |
| **Dev** | Every Blocking finding. Start with "Independent of the design" | Fix the findings in "Waits for the design" only after DESIGN.md is settled |
| **Owner** | "Design questions" and the verdict | Decide whether R1 and R13 go to the architect |

Design questions, both for the architect:

| Id | In short |
|---|---|
| R1 | `Task.status` is the caller's guess, not a fact. A task's location is found three different ways |
| R13 | DESIGN.md asks for a type guard that goes against ARCHITECTURE.md rule 6 |

Waits for the design, because these findings sit in code R1 would reshape:

| Id | Kind | Where |
|---|---|---|
| R3 | Blocking | `project_tasks.py` `create`: which refusal comes first |
| R6 | Blocking | the four composition roots |
| R7 | Blocking | `run.main` |
| R8 | Follow-up | `run.main` has no test |
| R10 | Blocking | `tests/test_task.py` helpers |
| R11 | Follow-up | `Status` values |
| R12 | Follow-up | `project_tasks.py` `create` |

Independent of the design:

| Id | Kind | Where |
|---|---|---|
| R4 | Blocking | `ProjectClone` move and commit |
| R9 | Blocking | `commands/task.py` `add_parser` |
| R2 | Follow-up | `ARCHITECTURE.md:15` |
| R5 | Follow-up | the PR description |

### TASK.md changed by another role
None. This round reviews TASK.md as of `1aeba97`. That commit is signed by the architect identity, which the planner shares, so the two can't be told apart. The only commit before it is `a137f7d`, `Add task wcf-0027`, made by the owner. This round also reviews against DESIGN.md, from `b1caefd`.

### Scope
The diff is `d8669a6...2585b62`, the merge-base with `origin/main`. It has two commits:
- `7d64b15` feat(task): close and reopen tasks, with notes split into open and closed
- `2585b62` docs(task): record the open and closed notes layout

### Checks
The Spec and Behaviour reviewers ran these in throwaway clones at 2585b62, after `uv sync --group dev`:

| Check | Result |
|---|---|
| `uv run pytest` (host tier) | 590 passed, 27 deselected |
| `uv run ruff check .` and `ruff format --check .` | clean, 146 files |
| `uv run mypy` | no issues in 98 files |
| `tests/test_docs.py` | passes |

### Design questions

#### R1: `Task.status` is the caller's guess, not a fact
Standards and Smells found this separately, and it has one cause. The evidence:
- **The status is a guess.** `Task.status` (`src/foundry/task.py:46-54`) holds what the caller expects; its docstring says "the repository decides". Callers build it from command-line input: `src/foundry/commands/run.py:38` builds `Task.as_open(args.task_id)` before `:44` checks whether the task is open.
- **Its uses read as fact.** `tests/test_run.py:143` gets "t1 is closed" from `require_open(..., task=Task.as_open("t1"))`.
- **It is only ever asserted, never used.** See `project_tasks.py:27`, `:50`, `:58` and `session.py:59`. Each callee already knows the value it asserts.
- **The location is found three ways:**
  - `create` loops over `Status`, calling `exists` on the checkout (`project_tasks.py:37-40`);
  - `_move` makes two `exists` calls (`:83-86`);
  - `is_closed` reads `TASK.md` from the branch, and ignores `task.status` (`:63`).

  The three can disagree. A closed dir with no `TASK.md` is "closed" to `close` and not closed to `run`.
- **"Status" is not in `GLOSSARY.md`.** AGENTS.md ("Docs") says to add a term when you introduce one.

Why it's a design question, quoting DESIGN.md:
- "A task's notes dir depends on a `Status` … carried by `Task` as an immutable field: `Task(id, status)`."
- "No lookup object, snapshot or precondition helper exists. This rules out … a `find` function."
- "A task's status is the caller's expectation, not a fact."
- "`is_closed` reads the closed task's `TASK.md`."

Who it costs: the next developer adding an operation that depends on the status, such as the list command TASK.md leaves out. They have to pick one of the three lookups or write a fourth, and remember that `task.status` may be wrong.

The question for the architect: should a `Task`'s status be a fact rather than a guess, and should a task's location be found in one place?
Fixed in `50180d1`. As DESIGN.md (85a2016) answers it: `ProjectTasks.get_task_by_id` is the one lookup, and builds the `Task` from the dir that exists. Every public method takes an id and returns a `Task`; the commands build none. The asserts and `is_closed` are gone. GLOSSARY.md's "Open task, Closed task" names `Status`.

#### R13: DESIGN.md asks for a type guard that goes against ARCHITECTURE.md rule 6
- **Rule 6** (`ARCHITECTURE.md:80`): "Fail fast, with a message; don't program defensively … Handle only the failures that have happened or that the design expects."
- **DESIGN.md:** "a non-`Status` is a `TypeError`". This gives `src/foundry/task.py:57-58`, plus its docstring line `:50` and its test `tests/test_task.py:116`.

The rule lets the design name the failures it expects, and DESIGN.md does name this one, so the guard is within the rule's letter. It still goes against the rule's intent:
- Every `Task` is built from a `Status` member.
- mypy checks `status: Status` in CI.
- No user can reach the guard, so it has no message for anyone.
- Every other `isinstance` check in `src/` validates outside data: config YAML, frontmatter, rulesets, GitHub's API, settings JSON. This is the only one that re-checks a typed argument.

The question for the architect: does the design expect this failure? R1's answer may settle this too, since it decides how a `Task` gets its status.
Fixed in `50180d1`. DESIGN.md now drops the guard: `Task.__post_init__` validates the id only, and its `TypeError` test is gone.

### Standards
- **R2 (Follow-up), stale launch description.** `ARCHITECTURE.md:15` says `foundry run` reads `agent-notes` only "Without ROLE". Since `src/foundry/commands/run.py:40-45`, it always clones, to refuse a closed task. Who hits it: someone working out why `foundry run PROJECT ROLE TASK` now needs access to the repository.
Fixed in `50180d1`. `ARCHITECTURE.md:15` says `run` finds the task on `agent-notes` and refuses a closed or missing one; the `project_tasks.py` codemap row names `get_task_by_id`.

Found clean:
- ADR 0012 supersedes ADR 0006's notes layout without editing it, and its row is added to `docs/adr/README.md`.
- The paths are spelled once, in `task.py` (design rule 1).
- `move_dir` stays inside `ProjectClone` (design rule 3).
- The glossary entries match the "Terms and decisions" section of TASK.md.

R1 and R13 are above.

### Spec
- **R3 (Blocking, waits for the design), `create` on a closed task's id doesn't name the dir.**
  - The criterion: "`foundry task create` refuses … when `.agent/tasks/open/<id>/` or `.agent/tasks/closed/<id>/` exists. The message names the existing dir."
  - `src/foundry/project_tasks.py:31-32` refuses on an existing `task/<id>` branch before the notes dirs are checked (`:37-40`).
  - `close` keeps `task/<id>`, as the task requires, so a closed task normally still has its branch.
  - A reproduction, closing `t5` and then running `create` on `t5`, gave `task t5 already exists: there is a task/t5 branch`. That message names neither dir and doesn't say the task is closed.
  - The test at `tests/test_task.py:194-204` passes only because its closed fixture `c0` has no `task/c0` branch.

  Who hits it: the owner reusing a closed task's id.
  Fixed in `50180d1`. `create_task` looks the task up before the branch check. `test_a_closed_task_that_kept_its_branch_is_refused_naming_its_notes_folder` covers it.
- **R8 (Follow-up, waits for the design), criterion 10 is shown only by reading `run.main`.** The criterion: "`foundry run PROJECT [ROLE] TASK` refuses a closed task, with or without ROLE, before creating or attaching any sandbox."
  - `tests/test_run.py:129-144` tests `require_open` on its own.
  - No test checks that `main` calls it before `prepare_launch` (`src/foundry/commands/run.py:44` before `:50`), on either path.

  The code is right today. Any change to `main`, from R1 or R7, could reorder it without a test failing.
  Fixed in `50180d1`. `main` now calls `role_to_launch` inside the scratch clone, then `prepare_launch`. `tests/test_run.py` runs `role_to_launch` against a real repository, with and without ROLE, for an open, a closed and a missing task.

Criteria met, with the evidence for each:

| Criterion | Evidence |
|---|---|
| 1. `create` writes to `open/` | `project_tasks.py:41`; the create test in `tests/test_task.py` |
| 2. `create` refuses on an existing dir | partial, see R3 |
| 3. Session variables | `Task.task_notes_dir`; `tests/test_session.py`, `tests/test_task_contract.py`; `AGENT_NOTES_ROOT` stays `.agent` |
| 4. `close` moves the dir unchanged, in one signed commit | `tests/test_task.py:359`. But see R4 |
| 5. `reopen` makes the reverse move | `tests/test_task.py:377` |
| 6, 7. The four refusals push nothing | `tests/test_task.py:398` |
| 8. No confirmation, `TURN`, PR check, branch, sandbox or `sessions/` | read in `_move`, `close_main` and `reopen_main`; branches unchanged in the test at `:359` |
| 9. No signing key | `tests/test_task.py:411` |
| 10. `run` refuses a closed task, with or without ROLE | partial, see R8 |
| 11. `run` reads `open/<id>/TURN` | `run.py:45`; `tests/test_run.py` |
| 12. README table and `agent-notes` row | `tests/test_docs.py` passes |
| 13. GLOSSARY.md and ADR 0012 | they match "Terms and decisions" |
| 14. The migration snippet in the PR | present in PR #34. It was run without `-S` on a toy bare repo: one commit, every move a 100% rename. A second run stops harmlessly at `commit` |
| 15. Host tier, ruff, mypy | pass, see Checks |

No scope creep.

### Behaviour
- **R4 (Blocking, independent), `close` and `reopen` can silently drop or rewrite notes files.**
  - `src/foundry/project_tasks.py:87-88` moves the dir in the checked-out files (`ProjectClone.move_dir`, `src/foundry/project_clone.py:88-97`). Then `commit` re-stages everything with `git add --all` (`project_clone.py:101`), under the owner's own git config.
  - A tracked notes file that matches the owner's global excludes (`core.excludesFile`) is deleted at the old path and never added at the new one.
  - With `core.autocrlf=input`, a file with CRLF line endings is rewritten.
  - The commit is still signed and pushed, with no message. This breaks "every file unchanged".

  Reproduced with the `tests/test_task.py` pattern: a real bare repo, a stand-in signer, an open task `t0` holding `TASK.md`, `run.log`, a CRLF file and an executable `sub/x.sh`, and `*.log` in a global excludes file. After `close`, `closed/t0/` had no `run.log`, and the CRLF file's blob had changed. The executable mode was kept. Who hits it: the owner, on a close or reopen, when their global excludes match a file an agent left in the notes. When it happens, the loss is silent.
Fixed in `50180d1`. `move_dir` stages the move with `git mv`, which keeps each blob and mode. `test_a_move_keeps_files_your_git_config_would_ignore_or_convert` reproduces your case (global `*.log` excludes, `core.autocrlf=input`, a CRLF file); it fails with the old `rename`. The old `move_dir` happy-path test is removed: `git mv` needs tracked files, and the close test covers a nested move.

Found sound:
- Every refusal raises before the commit and the push.
- `run` refuses a closed task before `prepare_launch`.
- With no `agent-notes` branch, `is_closed` returns false.
- Upper-case ids are lowercased.
- `move_dir`'s `FileExistsError` can't be reached.

### Smells
Who hits these: the next developer changing this code.

- **R7 (Blocking, waits for the design), one condition in three places: `run.main`.** In `src/foundry/commands/run.py:45-49`, "was a ROLE given?" is encoded three times:
  - `turn = tasks.read_turn(task) if role_name is None else None` (`:45`);
  - `if turn is not None:` (`:46`);
  - `assert role_name is not None` (`:49`), there only for mypy.

  `role_name` means "the ROLE given, or None" until `:47`, and "the role to launch" after it. At `d8669a6` this was a single `if role_name is None:` block. Anyone changing how the role is picked has to keep three statements in step.
  Fixed in `50180d1`. `role_to_launch` decides it once: `if role_name is None:` reads the turn. `require_open` is folded into it.
- **R6 (Blocking, waits for the design), duplicated composition roots.**
  - `close_main` (`src/foundry/commands/task.py:56-64`) and `reopen_main` (`:67-75`) are copies of each other. They differ only in the factory, the operation called and the lines printed.
  - The scratch-clone setup, `TemporaryDirectory` and then `ProjectTasks(ProjectClone.init(url, Path(scratch_dir), os.environ))`, appears at `commands/task.py:50-51`, `:60-61`, `:71-72` and `run.py:42-43`. Changing how a clone is built means four edits.
  - `create_main` prints through `report()` (`:78`), while `close_main` and `reopen_main` print inline.
  Fixed in `50180d1`. All four roots use `ProjectTasks.in_scratch_clone`. All three task commands print through one `report(action, project, task)`. `close_main` and `reopen_main` stay separate, five lines each, since sharing a body would need a switch on the action.
- **R9 (Blocking, independent), duplicated arguments in `add_parser`.** In `src/foundry/commands/task.py`, the PROJECT and TASK arguments are defined at `:23-24` for `create`, and again in the loop at `:38-41` for `close` and `reopen`. The loop variable `parser_` is named only to avoid clashing with the outer `parser`. Someone changing TASK's help can update one copy and miss the other.
Fixed in `50180d1`. PROJECT and TASK are defined once, in an argparse parent parser all three actions take.
- **R10 (Blocking, waits for the design), duplicated helpers and a misleading line in `tests/test_task.py`.**
  - `create()` (`:74-78`) and `tasks_of()` (`:305-308`) build the same scratch `ProjectTasks`.
  - The `ProjectClone` setup repeats in the `move_dir` tests (`:270-272`, `:280-282`, `:293-295`).
  - The signature assertion repeats at `:169-170`, `:372-373` and `:385-386`.
  - Close and reopen are picked by an `action` string twice (`:403-406`, `:417`).
  - `seed_notes` calls `tasks_of` for nothing at `:348`, and its comment ("clones nothing yet; the push below does the work") misleads.
  Fixed in `50180d1`. One `tasks_of` and one `clone_in` helper; `assert_notes_signed_with_your_key`; the refusal tests are parametrized by the `ProjectTasks` method; `seed_notes` became `push_notes(files)`, without the stray call.
- **R11 (Follow-up, waits for the design), `Status` values are paths.** At `src/foundry/task.py:40-41`, the members' values are dirs, so `self.status.value` at `:87` reads like a status but holds a path. `destination.status.name.lower()` at `src/foundry/project_tasks.py:84` uses the member name as message text, so renaming a member changes a user-facing message.
Fixed in `50180d1`. `Status` members are `auto()`; `task.py` maps each to its dir in `_STATUS_DIRS`. Messages spell "closed" and "open" themselves.
- **R12 (Follow-up, waits for the design), `existing` names a path not yet known to exist.** At `src/foundry/project_tasks.py:38`, so `:39` reads `if clone.exists(existing)`.
Fixed in `50180d1`. The loop is gone; `create_task` names the dir of the task `get_task_by_id` found.

Coverage. Each cell is `-` for checked with nothing found, or a finding id. MN is Mysterious Name, DC Duplicated Code, FE Feature Envy, DCl Data Clumps, PO Primitive Obsession, RS Repeated Switches, SS Shotgun Surgery, DvC Divergent Change, SG Speculative Generality, MC Message Chains, MM Middle Man, RB Refused Bequest.

| Item (file:line at HEAD) | MN | DC | FE | DCl | PO | RS | SS | DvC | SG | MC | MM | RB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| task.py:37 `Status` | R11 | - | - | - | - | - | - | - | - | - | - | - |
| task.py:45 `Task` | - | - | - | - | - | - | - | - | R1 | - | - | - |
| task.py:56 `__post_init__` | - | - | - | - | - | - | - | - | R13 | - | - | - |
| task.py:66 `from_id` | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:72 `as_open` | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:76 `as_closed` | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:85 `task_notes_dir` | R11 | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:14 `ProjectTasks` | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:20 `create` | R12 | R1 | - | - | - | R1 | - | - | R1 | - | - | - |
| project_tasks.py:45 `close` | - | - | - | - | - | - | - | - | R1 | - | - | - |
| project_tasks.py:53 `reopen` | - | - | - | - | - | - | - | - | R1 | - | - | - |
| project_tasks.py:61 `is_closed` | - | R1 | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:65 `read_turn` | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:79 `_move` | R11 | R1 | - | - | - | - | - | - | - | - | - | - |
| project_clone.py:88 `move_dir` | - | - | - | - | - | - | - | - | - | - | - | - |
| commands/task.py:13 `add_parser` | R9 | R9 | - | - | - | - | - | - | - | - | - | - |
| commands/task.py:44 `create_main` | - | R6 | - | - | - | - | R6 | - | - | - | - | - |
| commands/task.py:56 `close_main` | - | R6 | - | - | - | - | R6 | - | - | - | - | - |
| commands/task.py:67 `reopen_main` | - | R6 | - | - | - | - | R6 | - | - | - | - | - |
| run.py:35 `main` | R7 | R6 | - | - | - | - | - | - | - | - | - | - |
| run.py:56 `require_open` | - | - | - | - | - | - | - | - | - | - | - | - |
| session.py:57 `to_env` | - | - | - | - | - | - | - | - | R1 | - | - | - |
| session.py:75 `from_env` | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:74 `create` | - | R10 | - | - | - | - | - | - | - | - | - | - |
| test_task.py:305 `tasks_of` | - | R10 | - | - | - | - | - | - | - | - | - | - |
| test_task.py:346 `seed_notes` | R10 | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:277-299 `move_dir` tests | - | R10 | - | - | - | - | - | - | - | - | - | - |
| test_task.py:359, :377 close and reopen moves | - | R10 | - | - | - | - | - | - | - | - | - | - |
| test_task.py:398, :411 refusal tests | - | R10 | - | - | - | - | - | - | - | - | - | - |
| test_run.py:129 closed-task test | - | - | - | - | - | - | - | - | - | - | - | - |

### PR description
PR #34 follows the updated `pr` skill. The title has the `git-conventions` form, the Task section has the paths and one "For you to do" line, the Summary is two diffs, the Evidence names tests that exist, and the merge is a one-way door.
- **R5 (Follow-up, independent), Blast Radius overstates what `run` refuses.** The PR says that until the snippet runs, "`foundry run` and `close` refuse" every existing task. But `run` without ROLE fails with "has no turn". With ROLE, it starts a sandbox whose notes dir doesn't exist.
Fixed in the PR description. With `50180d1`, `run` refuses a missing task with or without ROLE, so Blast Radius now says `run`, `close` and `reopen` refuse each existing task as not existing until the snippet runs.

### Summary

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| Standards | 1 | 0 | R2, a stale ARCHITECTURE.md line |
| Spec | 2 | 1 | R3, `create` on a closed id doesn't name the dir |
| Behaviour | 1 | 1 | R4, a move can silently drop ignored files or rewrite CRLF ones |
| Smells | 6 | 4 | R7, one condition spread over three statements in `run.main` |
| Design questions | 2 | for the architect | R1, `Task.status` is a guess, found three ways |
| PR description | 1 | 0 | R5 |

Verdict: changes needed
