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

## Round 2 (reviewing 50180d1)

This round reviews the fix diff `12da10e..50180d1`. `12da10e` is a clean merge of `origin/main`, so `50180d1` is the only fix commit. It also reviews the DESIGN.md change `b1caefd..85a2016`, as part of the fix.

It follows the proposed form, as round 1 did, with all four axes: Standards, Spec, Behaviour and Smells. Smells returns a coverage table. A smell the fix introduces blocks when its fix is local. Every partial criterion is a finding. A first pass at this round used only three axes and approved. It was replaced before the dev's turn, at the owner's request. Finding ids continue from R13.

### Who reads what

| Role | Read | Then |
|---|---|---|
| **Dev** | R14 and R15, both Blocking | Fix them. The Follow-ups are yours to fix or to answer |
| **Owner** | The verdict, and R16 | Say whether R16, a rare line-ending rewrite on a move, should block |

There are no design questions this round.

### TASK.md changed by another role
None. The commits that changed TASK.md are still `a137f7d` (`Add task wcf-0027`, by the owner) and `1aeba97` (signed by the architect identity, which the planner shares). This round reviews TASK.md as of `1aeba97`. DESIGN.md is reviewed as of `85a2016`, also signed by the architect identity.

### Round 1 findings

| Id | Verdict | Evidence at HEAD |
|---|---|---|
| R1 | closed | `get_task_by_id` (`src/foundry/project_tasks.py:38`) is the one lookup. Every public method takes an id. `is_closed` and the status asserts are gone. GLOSSARY.md names `Status` |
| R2 | closed | `ARCHITECTURE.md:15` matches `run.main`'s order |
| R3 | closed | `create_task` looks the task up (`project_tasks.py:66-71`) before the branch check. `tests/test_task.py:214` uses a closed task with a real `task/c0` branch |
| R4 | closed | Rerun of the round 1 case (global `*.log`, `*.sh` and `sub/` excludes, `autocrlf=input`, CRLF and executable files, a nested dir): close made 5 pure renames and nothing else. Reopen restored the tree exactly. Also holds with a global `* text=auto` attribute. See R16 for a rarer variant |
| R5 | closed | PR #34's Blast Radius now matches `get_task_by_id` |
| R6 | closed | All four roots use `in_scratch_clone`: `run.py:38`, `commands/task.py:51`, `:60` and `:69`. All three task commands print through `report`. R14 is a new smell in that shared `report`, not R6 reopened |
| R7 | closed | `role_to_launch` decides "was a ROLE given?" once (`src/foundry/commands/run.py:62`) |
| R8 | closed | `tests/test_run.py:146`, `:154` and `:160` run `role_to_launch` against a real repository, with and without ROLE, for open, closed and missing tasks. See R19 for what remains shown only by reading |
| R9 | closed | One `task_arguments` parent parser (`commands/task.py:14-18`) |
| R10 | closed | One `tasks_of` and `clone_in` (`tests/test_task.py:75`, `:80`), `assert_notes_signed_with_your_key` (`:98`), refusal tests parametrized by method (`:447-472`), and `push_notes` (`:376`) |
| R11 | closed | `Status` uses `auto()`, and `_STATUS_DIRS` maps each status to its dir (`src/foundry/task.py:40-45`) |
| R12 | closed | The loop is gone |
| R13 | closed | The `isinstance` guard and its test are gone |

### Checks
The Spec and Behaviour reviewers ran these in throwaway clones at `50180d1`, after `uv sync --group dev`:

| Check | Result |
|---|---|
| `uv run pytest` (host tier) | 601 passed, 27 deselected |
| `uv run ruff check .` and `ruff format --check .` | clean, 146 files |
| `uv run mypy` | no issues in 98 files |
| `tests/test_docs.py` | passes |

### Standards
No new findings of its own. Standards also flagged R14 and R15, as smells; they are under Smells.

Checked clean:
- **Rule 1:** the paths are spelled only in `task.py`.
- **Rule 3:** `move_dir` goes through `ProjectClone`.
- **Rule 6:** `TaskNotFoundError` is caught only where DESIGN.md says.
- **Names:** the GLOSSARY.md and ARCHITECTURE.md codemap rows match the code.
- **Rule 7:** `ProjectTasks.in_scratch_clone` (`project_tasks.py:28-36`) builds the temporary clone, a job rule 7 gives to a command's `main`. DESIGN.md chose it to answer R6. Each `main` still builds the clone by calling it, and decides nothing, so this isn't a design question.

### Spec
- **R19 (Follow-up), criterion 10's "before creating or attaching any sandbox" is shown only by reading.**
  - The criterion: "`foundry run PROJECT [ROLE] TASK` refuses a closed task, with or without ROLE, before creating or attaching any sandbox."
  - The tests show that `role_to_launch` refuses (`tests/test_run.py:154`).
  - No test shows that `main` calls it (`src/foundry/commands/run.py:39`) before `prepare_launch` (`:46`).
  - DESIGN.md names `role_to_launch` as this criterion's seam, so it is not Blocking.

  Who hits it: a developer reordering `main`, rarely. Direction: accept as is, under DESIGN.md's seam. Testing `main` would need fakes for config, paths and sandbox, which is new machinery.

  Deferred: accepted as is, as the direction says. A test of `main` needs fakes for config, paths and the sandbox, which is the machinery DESIGN.md's seam avoids. Noted under Next in PROGRESS.md.
- **R20 (Follow-up), most of criterion 8 is shown only by reading.**
  - The criterion: "Neither `close` nor `reopen` asks for confirmation, reads `TURN`, checks the pull request, or touches `task/<id>`, sandboxes or `sessions/`."
  - Tested: branches are unchanged, and only the moved paths change (`tests/test_task.py:404`, `:409`, `:414`).
  - Shown only by reading: no prompt, no `TURN` read and no PR check (`commands/task.py` `close_main` and `reopen_main`; `project_tasks.py:86-125`).
  - Sandboxes and `sessions/` are out of reach by construction, since `ProjectTasks` holds only a `ProjectClone`.

  Who hits it: a developer adding a prompt or a `TURN` check to close later. Direction: accept as is, or add a test that runs `close_main` with no stdin.

  Deferred: accepted as is. `close_main` reads config and the foundry root, so a test of it needs the same fakes as R19. Noted under Next in PROGRESS.md.

The other criteria are met:

| # | Evidence |
|---|---|
| 1 | `project_tasks.py:73,81`; `tests/test_task.py:146` |
| 2 | `project_tasks.py:71`; `test_task.py:201`, `:214`; both dirs: `:361` |
| 3 | `Task.task_notes_dir`; `tests/test_session.py:47-49` |
| 4, 5 | `project_tasks.py:86-104`, `:121-126`; `test_task.py:396`, `:417`, `:428` |
| 6, 7 | `test_task.py:447-461`, each case checking nothing was pushed |
| 8 | partial, see R20 |
| 9 | `test_task.py:464-473` |
| 10 | partial, see R19 |
| 11 | `run.py:63`; `test_run.py:146` |
| 12 | `tests/test_docs.py:110` checks the command table. The `agent-notes` row (`README.md:56`) was grepped for the new layout |
| 13 | `GLOSSARY.md:48` and `:52`, `docs/adr/README.md:11` and ADR 0012 match "Terms and decisions" (grepped) |
| 14 | The snippet is in PR #34. Rerun on a toy bare repo: one commit, all 100% renames |
| 15 | See Checks |

There is no scope creep. `run` refusing a missing task, and the both-dirs error, are in DESIGN.md (85a2016).

### Behaviour
- **R16 (Follow-up), a move still rewrites CRLF files when your global gitattributes force text conversion.**
  - `move_dir` stages with `git mv` (`src/foundry/project_clone.py:98`).
  - `commit` then runs `git add --all` (`:102`). The checkout and the move fall within the same second, so git re-reads the moved files under your global attributes.
  - Reproduced 3 of 3 times. With a global `core.attributesFile` holding `* text eol=lf`, closing `t0` changed the blobs of a CRLF `.md` and `sub/run.sh` to LF.
  - This breaks "every file unchanged". `move_dir`'s docstring (`:92`) says your line-ending settings can't change a file.
  - The common `text=auto` forms are safe.

  Who hits it: an owner with an explicit, non-auto `text` attribute in their global gitattributes. That is rare. Direction: commit only what the move staged, or accept as is and correct the docstring.

  Docstring corrected in `55c7583`: it now names the `text` attribute that can still rewrite a file. Deferred: whether `commit` should stop running `add --all` after a move is the owner's call, as "Who reads what" says. It changes `ProjectClone.commit`'s contract, which `create_task` also relies on. Noted under Next in PROGRESS.md.

Found sound:
- the first create with no `agent-notes` branch;
- a repository with no commits;
- close, reopen and `read_task_turn` with no `agent-notes`;
- a task in both dirs (refused, nothing pushed);
- upper-case ids;
- a missing `closed/` parent;
- `in_scratch_clone` cleanup when the clone fails;
- `role_to_launch` refusing before `prepare_launch`.

### Smells
Who hits these: the next developer changing this code.

- **R14 (Blocking), Primitive Obsession and Repeated Switches: `report` decodes an action string.**
  - In `src/foundry/commands/task.py:76-85`, `report(action: str, ...)` looks up `_REPORTS[action]`.
  - Its callers pass the literals `"create"`, `"close"` and `"reopen"` (`:53`, `:62`, `:71`). Each `*_main` knows its action, encodes it as a string, and `report` decodes it again.
  - mypy can't check the string.
  - Because the literal sits in a composition root, no test checks that `close_main` passes `"close"` (rule 7). The test at `tests/test_task.py:273` checks the table only.
  - A mismatch raises a bare `KeyError` after `push_atomic` has succeeded: the task is closed, and you see a traceback.
  - At `2585b62` there was no switch; this was introduced by the fix, and the fix is local.

  Who hits it: a developer adding or renaming a task command, who edits `_REPORTS` and a literal in another function. Direction: pass `report` something mypy checks instead of a key.

  Fixed in `02c1903`. `report` takes an `Outcome` (a `NamedTuple`), and each `*_main` passes its constant: `CREATED`, `CLOSED` or `REOPENED`. mypy checks the name, and no lookup is left to fail after the push.
- **R15 (Blocking), hidden temporal coupling: `_move` relies on a checkout it doesn't do or name.**
  - At `2585b62`, `_move` checked out `agent-notes` itself. The fix removed that line.
  - `_move` (`src/foundry/project_tasks.py:121-126`) now moves, commits and pushes on whatever is checked out. It works only because `close_task` and `reopen_task` call `get_task_by_id` first, which checks out at `:44`.
  - `create_task` names that same dependency in a comment (`:69`). `_move` doesn't.

  Who hits it: a developer who makes `get_task_by_id` read without a checkout, as `read_task_turn` (`:112`) already does with `ProjectClone.read`. Close and reopen would then `git mv` on the default branch's checkout, failing with git's error and no hint why. Direction: make the dependency visible where `_move` relies on it.

  Fixed in `fa0fd7b`. `_move`'s docstring says it relies on `get_task_by_id` having checked out NOTES_BRANCH, so the move is made on the commit the task was found on. I kept it out of `_move`'s code: a second `check_out` would fetch again, and could move a task on a newer commit than the one it was found on.
- **R17 (Follow-up), Mysterious Name: `opened` and `closed` in `get_task_by_id`.**
  - `src/foundry/project_tasks.py:45` holds candidates, where the task would be. They aren't tasks found in that state.
  - The booleans `is_open` and `is_closed` sit beside them (`:46`).
  - The "doesn't exist" message at `:53-54` is built from `opened.id`.

  Who hits it: someone editing the lookup, at a low cost, since it is 15 lines. Direction: name them as candidates, or accept as is.

  Fixed in `4672f41`: `if_open` and `if_closed`.
- **R18 (Follow-up), Duplicated Code: three copies of the expected tree after a move.**
  - `tests/test_task.py:442-444` adds a third copy of the comprehension at `:408` and `:422`.

  Who hits it: someone changing how a move's expected tree is computed. Direction: one helper, or accept as is.

  Fixed in `d70a68a`: `moved(files, src, dst)`, used by all three tests.

Checked and not raised:
- **`close_task` and `reopen_task` (`:86-104`):** these mirror each other, but the shared part is already in `_move`.
- **`print("\n".join(report(...)))`:** this matches `commands/prune.py:22` and `commands/repo.py:48`.
- **`in_scratch_clone`:** a DESIGN.md decision, covered under Standards.
- **`from_id_and_status`:** DESIGN.md asks for it.

Coverage. Each cell is `-` for checked with nothing found, or a finding id. LF is Long Function, MN Mysterious Name, DC Duplicated Code, FE Feature Envy, DCl Data Clumps, PO Primitive Obsession, RS Repeated Switches, SS Shotgun Surgery, DvC Divergent Change, SG Speculative Generality, MC Message Chains, MM Middle Man, RB Refused Bequest. R15 sits under FE as its closest smell.

| Item (file:line at HEAD) | LF | MN | DC | FE | DCl | PO | RS | SS | DvC | SG | MC | MM | RB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| task.py:20-22 `OPEN_DIR`/`CLOSED_DIR` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:37 `Status` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:45 `_STATUS_DIRS` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:49 `Task` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:59 `__post_init__` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:67 `from_id_and_status` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:73 `as_open` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:77 `as_closed` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| task.py:86 `task_notes_dir` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:18 `TaskNotFoundError` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:22 `ProjectTasks` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:30 `in_scratch_clone` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:38 `get_task_by_id` | - | R17 | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:59 `create_task` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:86 `close_task` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:96 `reopen_task` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:106 `read_task_turn` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| project_tasks.py:121 `_move` | - | - | - | R15 | - | - | - | - | - | - | - | - | - |
| project_clone.py:88 `move_dir` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| session.py:57 `to_env` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| commands/task.py:10 `add_parser` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| commands/task.py:46 `create_main` | - | - | - | - | - | R14 | - | - | - | - | - | - | - |
| commands/task.py:57 `close_main` | - | - | - | - | - | R14 | - | - | - | - | - | - | - |
| commands/task.py:66 `reopen_main` | - | - | - | - | - | R14 | - | - | - | - | - | - | - |
| commands/task.py:76 `_REPORTS` | - | - | - | - | - | R14 | R14 | - | - | - | - | - | - |
| commands/task.py:83 `report` | - | - | - | - | - | R14 | R14 | - | - | - | - | - | - |
| commands/run.py:33 `main` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| commands/run.py:52 `role_to_launch` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_run.py:130 `tasks` fixture | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_run.py:146, :154, :160 `role_to_launch` tests | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:75 `clone_in`, :80 `tasks_of`, :85 `create` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:98 `assert_notes_signed_with_your_key` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:146-229 create tests | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:273 report test | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:283-297 parsing and `ProjectClone` tests | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:308-328 `turn_of` and turn tests | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:342-361 lookup tests | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:376 `push_notes`, :388 `tree` | - | - | - | - | - | - | - | - | - | - | - | - | - |
| test_task.py:396 close move | - | - | R18 | - | - | - | - | - | - | - | - | - | - |
| test_task.py:417 reopen move | - | - | R18 | - | - | - | - | - | - | - | - | - | - |
| test_task.py:428 move keeps files | - | - | R18 | - | - | - | - | - | - | - | - | - | - |
| test_task.py:456, :467 refusal and signing tests | - | - | - | - | - | - | - | - | - | - | - | - | - |

### Summary

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| Standards | 0 | 0 | none (R14 and R15 shared with Smells) |
| Spec | 2 | 0 | R19, criterion 10's ordering shown only by reading |
| Behaviour | 1 | 0 | R16, a forced `text` attribute rewrites CRLF files on a move |
| Smells | 4 | 2 | R14, `report` decodes an action string |
| Design questions | 0 | - | - |

Verdict: changes needed

## Round 3 (reviewing 55c7583)

This round reviews the fix diff `50180d1..55c7583`: `02c1903`, `fa0fd7b`, `4672f41`, `d70a68a` and `55c7583`. It uses the three axes of the current `code-review` skill: Standards, Spec and Behaviour. No ids are new this round, so the sequence continues from R20 next time.

### TASK.md changed by another role
None. The commits that changed TASK.md are still `a137f7d` (`Add task wcf-0027`, by the owner) and `1aeba97` (signed by the architect identity, which the planner shares). This round reviews TASK.md as of `1aeba97`, and DESIGN.md as of `85a2016`, also signed by the architect identity.

### Earlier findings

| Id | Verdict | Evidence at HEAD |
|---|---|---|
| R1–R13 | closed in round 2 | — |
| R14 | closed | `report` takes an `Outcome` (`src/foundry/commands/task.py:76`, `:88`). The callers pass `CREATED`, `CLOSED` and `REOPENED` (`:54`, `:63`, `:72`), which mypy checks. No lookup can fail after the push. The output text is unchanged (`tests/test_task.py:265-274`) |
| R15 | closed | `_move`'s docstring (`src/foundry/project_tasks.py:122-126`) names its reliance on `get_task_by_id`'s checkout. The direction was to make the dependency visible, and the reason given for not checking out again (a second fetch could move the task on a newer commit) is sound |
| R16 | deferred | The `move_dir` docstring (`src/foundry/project_clone.py:92-93`) now says what is true. Spec reproduced it: `* text` turns CRLF into LF on a move, while `* -text` and `* text=auto` keep CRLF. Whether `commit` should stop running `add --all` after a move is still the owner's call |
| R17 | closed | `if_open` and `if_closed` (`project_tasks.py:45`) read correctly at `:57`, beside `is_open` and `is_closed` |
| R18 | closed | `moved()` (`tests/test_task.py:396`) is used at `:413`, `:427` and `:447` |
| R19 | deferred | accepted as is, as round 2 says |
| R20 | deferred | accepted as is, as round 2 says |

### Checks
The Spec and Behaviour reviewers each ran these in a throwaway clone at `55c7583`, after `uv sync --group dev`:

| Check | Result |
|---|---|
| `uv run pytest` (host tier) | 601 passed, 27 deselected |
| `tests/test_docs.py` | 50 passed |
| `uv run ruff check .` and `ruff format --check .` | clean, 146 files |
| `uv run mypy` | no issues in 98 files |

### Standards
No new findings. Checked and not raised:
- `tests/test_task.py:397` says "notes dir", a term GLOSSARY.md lists under _Avoid_. The glossary's own "Open task" entry says "its notes dir" too, and the meaning is clear in a test helper.
- `moved()` replaces `src` anywhere in a path, not only as a prefix. No test data can trip on it.
- The module-level `CLOSED` sits beside `Status.CLOSED` and `task.CLOSED_DIR`. Each is qualified where it is used, so they don't get mixed up.

### Spec
No new findings. The fix diff adds no behaviour and changes no criterion's evidence. The round 2 table still holds, with criteria 8 and 10 partial, under the deferred R20 and R19. The new `move_dir` docstring is accurate against criterion 4, apart from R16. "Other than `auto`" also covers `-text`, which is harmless, so this wasn't raised.

### Behaviour
No new findings. These were found sound:
- `CREATED`, `CLOSED` and `REOPENED` hold the same text as the old `_REPORTS`. `report` in `prune.py` and `repo.py` is a separate function and isn't affected.
- The rename in `get_task_by_id` keeps both error messages and the return value.
- `_move` has no callers besides `close_task` and `reopen_task`, and both look the task up first.
- `moved()` computes the same trees as the three inline copies did.

### Summary
Standards 0, Spec 0, Behaviour 0: no new findings and none blocking. R16, R19 and R20 stay deferred. R16 is still waiting on the owner.

Verdict: approved
