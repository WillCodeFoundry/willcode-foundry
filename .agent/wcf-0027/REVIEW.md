# Review: wcf-0027

The owner asked for a fresh review with the updated `code-review` skill. This file was rewritten from scratch, and the earlier rounds are in the notes branch's history. Finding ids start again at R1.

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
- **R1 (Follow-up), possible Mysterious Name: `Task.status`.** At `src/foundry/task.py:46-54`, `status` holds the caller's expectation, not the task's real status. The uses read as fact:
  - `src/foundry/commands/run.py:38` builds `Task.as_open(args.task_id)` before line 44 checks whether the task is open.
  - `tests/test_run.py:143` gets "t1 is closed" from `require_open(..., task=Task.as_open("t1"))`.

  "Status" is also not in `GLOSSARY.md`, and AGENTS.md ("Docs") says to add a term you introduce. Downgraded from Blocking: DESIGN.md decides `Task(id, status)` and that "a task's status is the caller's expectation", and both docstrings say so. Who hits it: a later dev who reads `task.status` as fact. Direction: add "status" to the glossary as the expected notes location. Renaming is a design question for the owner.
- **R2 (Follow-up), stale launch description.** `ARCHITECTURE.md:15` says `foundry run` reads `agent-notes` only "Without ROLE". Since `src/foundry/commands/run.py:40-45`, it always clones, to refuse a closed task. Who hits it: someone working out why `foundry run PROJECT ROLE TASK` now needs access to the repository. Direction: mention the closed-task check in step 1.

- **R6 (Follow-up), possible Duplicated Code in the composition roots.** The reviewer added this after reading `src/foundry/commands/task.py`, because the Standards reviewer missed it.
  - `close_main` (`src/foundry/commands/task.py:56-64`) and `reopen_main` (`:67-75`) are the same function line for line. They differ only in the factory, the operation called and the two lines printed.
  - The scratch-clone setup, `tempfile.TemporaryDirectory(prefix=...)` and then `ProjectTasks(ProjectClone.init(url, Path(scratch_dir), os.environ))`, appears four times: `commands/task.py:50-51`, `:60-61`, `:71-72` and `src/foundry/commands/run.py:42-43`.

  Who hits it: the next dev who changes how foundry reaches a project, for example a new prefix or env, and has to edit four places. Direction: extract the scratch `ProjectTasks` once and share it, or accept as is, since DESIGN.md asks for "the same composition-root shape as `create_main`".

Dropped, because DESIGN.md decides them:
- The `isinstance(self.status, Status)` → `TypeError` guard (`task.py:57-58`), flagged under design rule 6. DESIGN.md: "a non-`Status` is a `TypeError`".
- `is_closed` testing for `TASK.md` while `create` and `_move` test for the dir, flagged as Duplicated Code. DESIGN.md: "`is_closed` reads the closed task's `TASK.md`".

Found clean:
- ADR 0012 supersedes ADR 0006's notes layout without editing it, and its row is added to `docs/adr/README.md`.
- The paths are spelled once, in `task.py` (design rule 1).
- `move_dir` stays inside `ProjectClone` (design rule 3).
- The glossary entries match the "Terms and decisions" section of TASK.md.
- Nothing is Speculative Generality.

### Spec
- **R3 (Blocking), `create` on a closed task's id doesn't name the dir.**
  - The criterion: "`foundry task create` refuses … when `.agent/tasks/open/<id>/` or `.agent/tasks/closed/<id>/` exists. The message names the existing dir."
  - `src/foundry/project_tasks.py:31-32` refuses on an existing `task/<id>` branch before the notes dirs are checked (lines 37-40).
  - `close` keeps `task/<id>`, as the task requires, so a closed task normally still has its branch.
  - A reproduction, closing `t5` and then running `create` on `t5`, gave `task t5 already exists: there is a task/t5 branch`. That message names neither dir and doesn't say the task is closed.
  - The test at `tests/test_task.py:194-204` passes only because its closed fixture `c0` has no `task/c0` branch.

  Who hits it: the owner reusing a closed task's id. That's rare, but it is the case the criterion describes. Direction: test a closed task that still has its branch, then make the refusal name the dir.

Criteria met, with the evidence for each:

| Criterion | Evidence |
|---|---|
| 1. `create` writes to `open/` | `project_tasks.py:41`; the create test in `tests/test_task.py` |
| 2. `create` refuses on an existing dir | partial, see R3 |
| 3. Session variables | `Task.task_notes_dir`; `tests/test_session.py`, `tests/test_task_contract.py`; `AGENT_NOTES_ROOT` stays `.agent` |
| 4. `close` moves the dir unchanged, in one signed commit | `tests/test_task.py:359`: the files, the title, one commit, the signature, branches unchanged. But see R4 |
| 5. `reopen` makes the reverse move | `tests/test_task.py:377` |
| 6, 7. The four refusals push nothing | `tests/test_task.py:398` |
| 8. No confirmation, `TURN`, PR check, branch, sandbox or `sessions/` | read in `_move`, `close_main` and `reopen_main`; branches unchanged in the test at `:359` |
| 9. No signing key | `tests/test_task.py:411`, the same pattern as `create`'s test at `:178` |
| 10. `run` refuses a closed task, with or without ROLE | `require_open` at `run.py:44` runs before `prepare_launch` at `:50`. It is tested at `tests/test_run.py:129`, and its order in `main` was checked only by reading |
| 11. `run` reads `open/<id>/TURN` | `run.py:45`; `tests/test_run.py` |
| 12. README table and `agent-notes` row | `tests/test_docs.py` passes |
| 13. GLOSSARY.md and ADR 0012 | they match "Terms and decisions", including the "Projects and tasks" row |
| 14. The migration snippet in the PR | present in PR #34. It was run without `-S` on a toy bare repo: one commit, every move a 100% rename, pushed. A second run stops at `commit` with nothing to commit, which does no harm |
| 15. Host tier, ruff, mypy | pass, see Checks |

No scope creep. The `ARCHITECTURE.md` codemap rows and the assertion in `session.py` are asked for in DESIGN.md.

### Behaviour
- **R4 (Blocking), `close` and `reopen` can silently drop or rewrite notes files.**
  - `src/foundry/project_tasks.py:87-88` moves the dir in the checked-out files (`ProjectClone.move_dir`, `src/foundry/project_clone.py:88-97`). Then `commit` re-stages everything with `git add --all` (`project_clone.py:101`).
  - That add runs under the owner's own git config, which `ProjectClone` is given so that commits are signed.
  - A tracked notes file that matches the owner's global excludes (`core.excludesFile`) is deleted at the old path and never added at the new one.
  - With `core.autocrlf=input`, a file with CRLF line endings is rewritten.
  - The commit is still signed and pushed, with no message. This breaks "every file unchanged".

  Reproduced with the `tests/test_task.py` pattern: a real bare repo, a stand-in signer, an open task `t0` holding `TASK.md`, `run.log`, a CRLF file and an executable `sub/x.sh`, and `*.log` in a global excludes file. After `close`, `closed/t0/` had no `run.log`, and the CRLF file's blob had changed (`c30dea8` became `422c2b7`). The executable mode was kept.

  Who hits it: the owner, on any close or reopen, when their global excludes match a file an agent left in the notes. Excludes like `*.log`, `.env*` and `*.swp` are common. Notes are mostly `.md`, so the match is the uncommon part. When it happens, the loss is silent. Direction: move the files in git's index, so that ignore rules and line-ending filters never apply. Test first, with an ignored file and a CRLF file, and check that the blobs and modes are identical after the move.

Found sound:
- Every refusal raises before the commit and the push: already closed, already open, doesn't exist, no signing key, and no `agent-notes` branch.
- `run` refuses a closed task, with or without ROLE, before `prepare_launch`.
- With no `agent-notes` branch, `is_closed` returns false.
- Upper-case ids are lowercased.
- `move_dir`'s `FileExistsError` can't be reached.

Left alone, as out of scope: tasks still in the old `.agent/<id>/` layout, and closing a task while its session is still pushing notes.

### PR description
PR #34 follows the updated `pr` skill. The title has the `git-conventions` form, the Task section has the paths and one "For you to do" line, the Summary is two diffs, the Evidence names tests that exist, and the merge is a one-way door. The extra "Migration" section is needed for criterion 14.
- **R5 (Follow-up), Blast Radius overstates what `run` refuses.** The PR says that until the snippet runs, "`foundry run` and `close` refuse" every existing task. But `run` without ROLE fails in `read_turn` with "has no turn". With ROLE it starts a sandbox whose `AGENT_TASK_NOTES_DIR` doesn't exist on `agent-notes`. Who hits it: the owner merging and then running `foundry run` before the snippet. Direction: say so, and say to run the snippet before any `foundry run`.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| Standards | 3 | 0 | R1, `Task.status` reads as fact |
| Spec | 1 | 1 | R3, `create` on a closed id doesn't name the dir |
| Behaviour | 1 | 1 | R4, a move can silently drop ignored files or rewrite CRLF ones |
| PR description | 1 | 0 | R5 |

Verdict: changes needed
