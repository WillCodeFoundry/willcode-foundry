# Review: wcf-0027

The owner asked for a fresh review with the updated `code-review` skill. This file was rewritten from scratch, and the earlier rounds are in the notes branch's history. Finding ids start again at R1.

This round follows the **proposed** form of the review, at the owner's request (see the `[proposal]` entries in LEARNINGS.md). It differs from the current skill in four ways:
- There is a fourth reviewer, **Smells**, which returns a coverage table.
- A smell the diff introduces blocks when its fix is local.
- Findings whose fix would change a DESIGN.md decision go to the owner as **design questions**.
- With a design question open, `TURN` goes to `human`.

## Round 1 (reviewing 2585b62)

The diff is `d8669a6...2585b62`, the merge-base with `origin/main`. It has two commits:
- `7d64b15` feat(task): close and reopen tasks, with notes split into open and closed
- `2585b62` docs(task): record the open and closed notes layout

### TASK.md changed by another role
None. This round reviews TASK.md as of `1aeba97`. That commit is signed by the architect identity, which the planner shares, so the two can't be told apart. The only commit before it is `a137f7d`, `Add task wcf-0027`, made by the owner. This round also reviews against DESIGN.md, from `b1caefd`.

### Checks
The Spec and Behaviour reviewers ran these in throwaway clones at 2585b62, after `uv sync --group dev`:

| Check | Result |
|---|---|
| `uv run pytest` (host tier) | 590 passed, 27 deselected |
| `uv run ruff check .` and `ruff format --check .` | clean, 146 files |
| `uv run mypy` | no issues in 98 files |
| `tests/test_docs.py` | passes |

### Standards
- **R2 (Follow-up), stale launch description.** `ARCHITECTURE.md:15` says `foundry run` reads `agent-notes` only "Without ROLE". Since `src/foundry/commands/run.py:40-45`, it always clones, to refuse a closed task. Who hits it: someone working out why `foundry run PROJECT ROLE TASK` now needs access to the repository. Direction: mention the closed-task check in step 1.

Found clean:
- ADR 0012 supersedes ADR 0006's notes layout without editing it, and its row is added to `docs/adr/README.md`.
- The paths are spelled once, in `task.py` (design rule 1).
- `move_dir` stays inside `ProjectClone` (design rule 3).
- The glossary entries match the "Terms and decisions" section of TASK.md.

R1 is now a design question, below. The rule 6 point is design question R13.

### Spec
- **R3 (Blocking), `create` on a closed task's id doesn't name the dir.**
  - The criterion: "`foundry task create` refuses … when `.agent/tasks/open/<id>/` or `.agent/tasks/closed/<id>/` exists. The message names the existing dir."
  - `src/foundry/project_tasks.py:31-32` refuses on an existing `task/<id>` branch before the notes dirs are checked (lines 37-40).
  - `close` keeps `task/<id>`, as the task requires, so a closed task normally still has its branch.
  - A reproduction, closing `t5` and then running `create` on `t5`, gave `task t5 already exists: there is a task/t5 branch`. That message names neither dir and doesn't say the task is closed.
  - The test at `tests/test_task.py:194-204` passes only because its closed fixture `c0` has no `task/c0` branch.

  Who hits it: the owner reusing a closed task's id. Direction: test a closed task that still has its branch, then make the refusal name the dir.
- **R8 (Follow-up), criterion 10 is shown only by reading `run.main`.** The criterion: "`foundry run PROJECT [ROLE] TASK` refuses a closed task, with or without ROLE, before creating or attaching any sandbox."
  - `tests/test_run.py:129-144` tests `require_open` on its own.
  - That `main` calls it before `prepare_launch` (`src/foundry/commands/run.py:44` before `:50`), on both paths, is checked by no test.

  The code is right today, so this is a Follow-up. But the fix for R7 reorders `main`, so add the test before that fix. Direction: test `main` against the host and sbx fakes the host tier already has, for a closed task with and without ROLE.

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
- **R4 (Blocking), `close` and `reopen` can silently drop or rewrite notes files.**
  - `src/foundry/project_tasks.py:87-88` moves the dir in the checked-out files (`ProjectClone.move_dir`, `src/foundry/project_clone.py:88-97`). Then `commit` re-stages everything with `git add --all` (`project_clone.py:101`), under the owner's own git config.
  - A tracked notes file that matches the owner's global excludes (`core.excludesFile`) is deleted at the old path and never added at the new one.
  - With `core.autocrlf=input`, a file with CRLF line endings is rewritten.
  - The commit is still signed and pushed, with no message. This breaks "every file unchanged".

  Reproduced with the `tests/test_task.py` pattern: a real bare repo, a stand-in signer, an open task `t0` holding `TASK.md`, `run.log`, a CRLF file and an executable `sub/x.sh`, and `*.log` in a global excludes file. After `close`, `closed/t0/` had no `run.log`, and the CRLF file's blob had changed. The executable mode was kept. Who hits it: the owner, on a close or reopen, when their global excludes match a file an agent left in the notes. Direction: move the files in git's index, so that ignore rules and line-ending filters never apply. Test first, with an ignored file and a CRLF file, and check that the blobs and modes are identical after the move.

Found sound:
- Every refusal raises before the commit and the push.
- `run` refuses a closed task before `prepare_launch`.
- With no `agent-notes` branch, `is_closed` returns false.
- Upper-case ids are lowercased.
- `move_dir`'s `FileExistsError` can't be reached.

### Smells
Who hits these: the next developer changing this code.

- **R7 (Blocking), Mysterious Name / one condition in three places: `run.main`.** In `src/foundry/commands/run.py:45-49`, "was a ROLE given?" is encoded three times:
  - `turn = tasks.read_turn(task) if role_name is None else None` (`:45`);
  - `if turn is not None:` (`:46`);
  - `assert role_name is not None` (`:49`), only for mypy.

  `role_name` means "the ROLE given, or None" until `:47`, and "the role to launch" after it. At `d8669a6` this was one `if role_name is None:` block. Direction: restore one `if role_name is None:` branch inside the `with`, dropping the sentinel and the assert. DESIGN.md's "one `ProjectTasks`, reused for `read_turn`" still holds. Add R8's test first.
- **R6 (Blocking), Duplicated Code / Shotgun Surgery: the composition roots.**
  - `close_main` (`src/foundry/commands/task.py:56-64`) and `reopen_main` (`:67-75`) are copies of each other. They differ only in the factory, the operation called and the lines printed.
  - The scratch-clone setup, `TemporaryDirectory` and then `ProjectTasks(ProjectClone.init(url, Path(scratch_dir), os.environ))`, appears at `commands/task.py:50-51`, `:60-61`, `:71-72` and `run.py:42-43`. Changing how a clone is built means four edits.
  - `create_main` prints through `report()` (`:78`), while `close_main` and `reopen_main` print inline.

  Direction: one local helper that gives a project's `ProjectTasks`, used by all four, and one way of printing the result.
- **R9 (Blocking), Duplicated Code: `add_parser`.** In `src/foundry/commands/task.py`, the PROJECT and TASK arguments are defined at `:23-24` for `create`, and again in the loop at `:38-41` for `close` and `reopen`. The loop variable `parser_` is named only to avoid the outer `parser`. Who hits it: someone changing TASK's help updates one copy and not the other. Direction: run `create` through the same loop, and give the loop variable a real name.
- **R10 (Blocking), Duplicated Code and a misleading line in `tests/test_task.py`.**
  - `create()` (`:74-78`) and `tasks_of()` (`:305-308`) build the same scratch `ProjectTasks`.
  - The `ProjectClone` setup repeats in the `move_dir` tests (`:270-272`, `:280-282`, `:293-295`).
  - The signature assertion repeats at `:169-170`, `:372-373` and `:385-386`.
  - Close and reopen are picked by an `action` string twice (`:403-406`, `:417`).
  - `seed_notes` calls `tasks_of` for nothing at `:348`, and its comment ("clones nothing yet; the push below does the work") misleads.

  Direction: build `create` on `tasks_of`, share one signature-check helper, parametrize on the operation instead of a string, and delete `:348`.
- **R11 (Follow-up), Mysterious Name: `Status` values are paths.** At `src/foundry/task.py:40-41`, the members' values are dirs, so `self.status.value` at `:87` reads like a status but holds a path. `destination.status.name.lower()` at `src/foundry/project_tasks.py:84` uses the member name as message text, so renaming a member changes a message. Direction: a named property for the dir, and spell the word in the message. Or accept as is.
- **R12 (Follow-up), Mysterious Name: `existing`.** At `src/foundry/project_tasks.py:38`, `existing` names a path before the code knows whether it exists, so `:39` reads `if clone.exists(existing)`. Direction: name it for what it holds, a candidate notes dir.

Coverage. Each cell is `-` for checked with nothing found, or a finding id. MN is Mysterious Name, DC Duplicated Code, FE Feature Envy, DCl Data Clumps, PO Primitive Obsession, RS Repeated Switches, SS Shotgun Surgery, DvC Divergent Change, SG Speculative Generality, MC Message Chains, MM Middle Man, RB Refused Bequest.

| Item (file:line at HEAD) | MN | DC | FE | DCl | PO | RS | SS | DvC | SG | MC | MM | RB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| task.py:37 `Status` | R11 | - | - | - | - | - | - | - | - | - | - | - |
| task.py:45 `Task` | - | - | - | - | - | - | - | - | R1 | - | - | - |
| task.py:56 `__post_init__` | - | - | - | - | - | - | - | - | - | - | - | - |
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

### Design questions, for the owner
These would change a DESIGN.md decision. The dev doesn't fix them. The owner sends them to the architect, or accepts the code as is.

- **R1, `Task.status` is an expectation that reads as a fact, and "where is this task?" is asked three ways.** This merges Standards and Smells, which found the same cause.
  - `Task.status` (`src/foundry/task.py:46-54`) holds what the caller expects. Its uses read as fact: `run.py:38` builds `Task.as_open` before `:44` checks, and `tests/test_run.py:143` gets "t1 is closed" from `Task.as_open("t1")`.
  - The status is only ever asserted (`project_tasks.py:27`, `:50`, `:58`, `session.py:59`), so it carries a value each callee already knows.
  - The location is found three ways: `create` loops over `Status` calling `exists` (`project_tasks.py:37-40`), `_move` makes two `exists` calls (`:83-86`), and `is_closed` reads `TASK.md` from the branch, ignoring `task.status` (`:63`).
  - "Status" is not in `GLOSSARY.md`, and AGENTS.md ("Docs") asks for it.

  DESIGN.md decides this: "carried by `Task` as an immutable field: `Task(id, status)`", "No lookup object, snapshot or precondition helper exists… rules out… a `find` function", and "`is_closed` reads the closed task's `TASK.md`". Cost: whoever adds the next status-dependent operation, such as the list command TASK.md leaves out, writes a fourth shape. Options:
  - accept it, and only add "status" to the glossary (the dev can do that);
  - ask the architect for one way to find a task's location, which would mean dropping `status` from `Task` or making it a fact.
- **R13, DESIGN.md asks for a guard that `ARCHITECTURE.md` rule 6 forbids.**
  - Rule 6: "Fail fast…; don't program defensively… Handle only the failures that have happened or that the design expects."
  - DESIGN.md: "a non-`Status` is a `TypeError`". This gives `src/foundry/task.py:57-58`, where `isinstance(self.status, Status)` repeats what mypy already enforces, and no user can reach it.

  Options: accept it, or have the architect drop the line so the dev can delete the guard and its docstring line (`task.py:50`).

### PR description
PR #34 follows the updated `pr` skill. The title has the `git-conventions` form, the Task section has the paths and one "For you to do" line, the Summary is two diffs, the Evidence names tests that exist, and the merge is a one-way door.
- **R5 (Follow-up), Blast Radius overstates what `run` refuses.** The PR says that until the snippet runs, "`foundry run` and `close` refuse" every existing task. But `run` without ROLE fails with "has no turn". With ROLE it starts a sandbox whose notes dir doesn't exist. Direction: say so, and say to run the snippet before any `foundry run`.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| Standards | 1 | 0 | R2, a stale ARCHITECTURE.md line |
| Spec | 2 | 1 | R3, `create` on a closed id doesn't name the dir |
| Behaviour | 1 | 1 | R4, a move can silently drop ignored files or rewrite CRLF ones |
| Smells | 6 | 4 | R7, one condition spread over three statements in `run.main` |
| Design questions | 2 | for the owner | R1, `Task.status` and the three lookups |
| PR description | 1 | 0 | R5 |

Blocking for the dev: R3, R4, R6, R7, R9, R10. For the owner: R1 and R13.

Verdict: changes needed
