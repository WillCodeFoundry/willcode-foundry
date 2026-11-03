# Review

## Round 1 (reviewing 1ab21bc)

`TASK.md` history: no commit by another role. `8545a3f` created the task (the human, `Add task wcf-0028`, signed `G`). `e3b591a` is signed `G` by the planner's identity, which the planner shares with the architect, so it can't be told apart from an architect commit. This round reviews against `e3b591a`. The task has no `DESIGN.md`.

Diff: `git diff f6c10e1...1ab21bc` (45377dd, 9836f09, 1ab21bc). pytest (host tier, `tests/test_docs.py` included), ruff and mypy pass in a throwaway clone.

### Standards

**R1 · Blocking · `list_main` decides, against design rule 7** (`src/foundry/commands/task.py:95-110`)
- `ARCHITECTURE.md` rule 7 says a composition root only builds and passes, and logic in `main` is logic no test reaches.
- `list_main` holds the per-project `try/except (FoundryError, GitError)` that makes a failure into a `ProjectListing` error value. That is the rule "a failed project is reported and the rest are still listed".
- No test reaches it: in `tests/test_task.py`, `list_main` appears only in the parser's `set_defaults` wiring. `repo.py` keeps the equivalent catch out of `main` (`repo.py:58`), in a function the tests call.
- Who hits it: the next dev who narrows or moves that `except`, with no test to fail.
- Direction: move the per-project catch into a function the tests call with their own clone, and leave `main` to build, loop and print. Shares a cause with R3.

**R2 · Follow-up · `project_tasks.py`'s module docstring no longer matches the code** (`src/foundry/project_tasks.py:1-5`)
- The docstring still lists "finding, creating, closing and reopening them, and reading their turn", with no listing. It also says "every other operation goes through" `get_task_by_id`.
- `list_open_task_summaries` doesn't go through `get_task_by_id`, by design: avoiding a fetch per task is the point.
- Who hits it: a reader of the module, who would think listing costs a fetch per task.
- Direction: add listing to the summary, and name it as the exception to "goes through `get_task_by_id`".

### Spec

All acceptance criteria are met, each by code and a test in `tests/test_task.py`: columns, name order and dedup, `--turn`, closed tasks and stray files, both no-tasks lines, each failure case, the symlinked `TURN`, the fetch count, the clone seams, and the docs. No scope creep: `read`, `read_task_turn` and `in_scratch_clone` keep their behaviour.

**R3 · Follow-up · the exit code and the stdout/stderr split aren't shown end to end** (`src/foundry/commands/task.py:95-110`)
- Spec: "`error: PROJECT: <message>` on stderr, the remaining projects are still listed, and the command exits 1".
- The lines themselves are tested through `listing_lines`. Three things aren't tested: the per-project catch, the exit code, and which stream each line goes to.
- "Seams to test" doesn't name `list_main`, so this is a Follow-up, not partial.
- Who hits it: a later edit that moves the `try` outside the loop, or prints errors on stdout as `repo.py` does.
- Direction: once R1 moves the catch out, test it over one good and one failing project. Shares a cause with R1.

### Behaviour

I built real repositories and reproduced each case.

Behaves as specified:
- An unreachable URL fails that project only; git's multi-line message is carried.
- A missing, blank or directory `TURN` fails the project.
- Invalid dir names (spaces, upper case) fail the project.
- A project with only closed tasks prints `no open tasks`.
- A symlinked `TURN` shows its target name and reads nothing outside the clone.
- CRLF in `TURN` is stripped.
- Columns align across ids of different widths.

**R4 · Follow-up · a multi-line `TURN` breaks one line per task** (`src/foundry/commands/task.py:158`, `src/foundry/project_tasks.py:166`)
- A `TURN` holding `dev\nextra\n` prints `PROJECT  t2  dev`, then `extra` on a line of its own. Reproduced.
- [ADR 0011](docs/adr/0011-turn-is-one-line.md) makes `TURN` one line, so only a hand-edited `TURN` does this, and rarely.
- Direction: accept as is, or show the first line only.

**R5 · Follow-up · the missing-`TURN` message gives `run`'s fix in a listing** (`src/foundry/project_tasks.py:168-171`)
- `task list` prints `error: P: task t2 has no turn: ... Name the role to run instead.` Reproduced.
- In a listing, the fix is to write `TURN` on `agent-notes`, and the whole project stays hidden until then.
- `TASK.md` asks for both "wording shared with `read_task_turn`" and a message that "says how to fix it", and this follows the first.
- Who hits it: anyone with one broken task, now and then.
- Direction: share the first part of the message and let each caller add its own fix, or accept as is.

### Smells

| Function | Verdict |
|---|---|
| `commands/task.py:add_parser` | clean |
| `commands/task.py:list_main` | clean (its rule-7 problem is R1) |
| `commands/task.py:ProjectListing` | clean |
| `commands/task.py:list_projects` | clean |
| `commands/task.py:listing_lines` | R7 |
| `project_clone.py:MissingPathError` | clean |
| `project_clone.py:fetch_branch` | clean |
| `project_clone.py:local_list_dir` | R8 |
| `project_clone.py:local_read` | R8 |
| `project_clone.py:_require_fetched`, `_object_type` | clean |
| `project_clone.py:_local_ref` | R8 |
| `project_tasks.py:TaskSummary` | clean |
| `project_tasks.py:read_task_turn` | clean, and simpler than at `f6c10e1` |
| `project_tasks.py:list_open_task_summaries` | R6 |
| `project_tasks.py:_turn_of` | clean |

**R6 · Blocking · possible Long Function: `list_open_task_summaries`** (`src/foundry/project_tasks.py:122-149`)
- It does four things at different levels of detail: fetch, list, check each dir name is a task id, and read each turn.
- The id check (136-143) builds the `Task`, compares ids to catch `as_open`'s lowercasing, then wraps the error in a second `FoundryError`.
- The `MissingPathError` → `None` read at 144-147 is a second nested `try` in the same loop.
- Who hits it: the next dev to change the id rules or the read.
- Direction: extract the id check into a function of its own, with an honest name.

**R7 · Blocking · possible Long Function: `listing_lines`** (`src/foundry/commands/task.py:145-168`)
- It filters, chooses the no-tasks lines, builds rows, works out the widths and renders.
- It does this by splitting every project into three parallel lists (`rows`, `notes`, `errors`). Lines 166-167 then regroup the rows and notes by project, scanning every list for each project.
- Who hits it: the next dev to change the output or add a column.
- Direction: work out the widths first, then render each project's lines from its own listing in one pass.

**R8 · Follow-up · possible Duplicated Code: the remote ref spelled three ways** (`src/foundry/project_clone.py:74`, `:163`, `:177-179`)
- The diff adds `_local_ref`, but `read` (74) and `push_atomic` (163) still spell `refs/remotes/{_REMOTE_NAME}/…` inline.
- `local_list_dir` and `local_read` also open with the same three lines.
- Who hits it: the next dev to change how remote refs are named.
- Direction: have `read` and `push_atomic` use `_local_ref`. `TASK.md` rules out changing `read`'s behaviour, not its internals.

### Names

No findings. Every name the diff adds is clean against `GLOSSARY.md` and the repository's existing uses:
- `MissingPathError`
- `fetch_branch`, `local_list_dir`, `local_read`
- `_require_fetched`, `_object_type`, `_local_ref`
- `TaskSummary` and its fields
- `list_open_task_summaries`, `_turn_of`
- `list_main`, `list_parser`
- `ProjectListing` and its fields
- `list_projects`, `listing_lines`
- `--turn ROLE`
- the help text, and the README and `ARCHITECTURE.md` prose

`NAMES.md` records each choice.

### Design questions

None.

Summary: Standards 2 (1 blocking; worst: R1, logic in a composition root). Spec 1 (0 blocking; worst: R3, exit code untested). Behaviour 2 (0 blocking; worst: R5, the fix hint in the error message). Smells 3 (2 blocking; worst: R7, `listing_lines`). Names 0. No design questions open.

Verdict: changes needed

## Round 2 (reviewing 294b4af)

`TASK.md` history: unchanged since round 1, and no commit by another role. `8545a3f` created the task (the human, signed `G`). `e3b591a` is signed `G` by the planner's identity, which the planner shares with the architect. This round reviews against `e3b591a`. The task has no `DESIGN.md`.

Fix diff: `git diff 1ab21bc...294b4af` (4195ec5, 87a4ac7, 8e7f8d6, 294b4af). The default branch has no new commits since `f6c10e1`. In a throwaway clone, pytest passes (host tier: 644 passed), and so do ruff (check and format) and mypy.

### Earlier findings

| Id | Verdict | Why |
|---|---|---|
| R1 | closed | The per-project catch is now `read_project_listing` (`src/foundry/commands/task.py:139-148`), and the tests call it directly (`tests/test_task.py:743`). `list_main` (`task.py:95-104`) only builds, maps, prints, and exits 1 when there are stderr lines, as TASK.md gives `main`. |
| R2 | closed | The docstring at `src/foundry/project_tasks.py:1-7` names listing, and says it is the one-fetch exception to `get_task_by_id`. |
| R3 | closed | `tests/test_task.py:754` runs `cli.main(["task", "list"])`. The failing project sorts first, so moving the catch outside the loop would fail the test. It checks exit 1, the exact stdout and the one `error:` line on stderr, then exit 0 with clean stderr when only the good project is named. |
| R4 | deferred | ADR 0011 makes `TURN` one line. Only a hand-edited `TURN` hits this. It loses no work, and a first-line-only rule would be a decision of its own. One correction to the dev's reasoning: a listing-only rule wouldn't need to change `read_task_turn`. |
| R5 | closed | `_turn_of(..., fix=...)` (`project_tasks.py:172`) holds the shared first part of the message. `read_task_turn` keeps "Name the role to run instead." (`:121`), so its message is unchanged from `f6c10e1`. Listing ends "Write the next role's name in it." (`:143`), and `tests/test_task.py:625` pins that ending. |
| R6 | closed | `list_open_task_summaries` (`project_tasks.py:123`) fetches, lists and maps. The id check is now `_open_task_in_dir` (`:158`) and the turn read is `_read_local_task_summary` (`:137`). |
| R7 | closed | `listing_lines` (`task.py:151`) filters, works out the two widths, then renders each project in one pass. The parallel lists and the regrouping are gone. |
| R8 | closed | `read` and `push_atomic` use `_local_ref` (`src/foundry/project_clone.py:74`, `:163`). `refs/remotes/{_REMOTE_NAME}` is now spelled only in `_local_ref`, and both build the same strings as before. |

### Standards

No new findings. The fix diff keeps the design rules:
- Rule 1: paths are spelled only through `OPEN_DIR`, `NOTES_BRANCH` and `TURN_FILE`.
- Rule 6: each project's error is a value, and only the entry point prints.
- Rule 7: covered under R1 above.
- Rule 3: the new end-to-end test uses `monkeypatch.chdir` and `setenv`. That sets the environment, as `tests/conftest.py` and `tests/test_skills.py` already do; it doesn't replace any code, and it runs real git, so it doesn't break the rule.

### Spec

No new findings. Every acceptance criterion is still met after the fixes. `read_task_turn`'s behaviour and `ProjectClone.read`'s behaviour are unchanged, as TASK.md requires, and the invalid-id tests still pass.

### Behaviour

No new findings. I reproduced these against the fix diff:
- `listing_lines` over a mix of projects (long name, failed, two tasks, none), with no filter and with three `--turn` values. Columns are sized over printed task lines only and stay aligned. Both no-tasks lines and the stderr error lines are correct.
- `_open_task_in_dir` refuses `WCF-1`, `.x`, `a..b` and `é`, each with a reason and ending "Rename or remove it.", and accepts `wcf-1`.
- The `_local_ref` change builds the same ref strings as before.

### Smells

| Function | Verdict |
|---|---|
| `commands/task.py:list_main` | clean; R1 closed |
| `commands/task.py:read_project_listing` | new, clean |
| `commands/task.py:listing_lines` | clean; R7 closed |
| `commands/task.py:_with_turn` | new, clean |
| `project_tasks.py:read_task_turn` | clean |
| `project_tasks.py:list_open_task_summaries` | clean; R6 closed |
| `project_tasks.py:_read_local_task_summary` | new, clean |
| `project_tasks.py:_open_task_in_dir` | new, clean |
| `project_tasks.py:_turn_of` | clean; `fix` has two real callers, so it isn't speculative |
| `project_clone.py:read`, `push_atomic` | clean; R8 closed |
| the two new tests in `tests/test_task.py` | new, clean |

No new findings.

### Names

All clean:
- `read_project_listing` (renamed from `list_project`)
- `_read_local_task_summary`
- `_open_task_in_dir`
- `_with_turn`
- `_turn_of` and its `fix` keyword
- the locals: `dir_name`, `reason`, `listed`, `name_width`, `id_width`
- the two new tests
- the new docstring prose

The sub-review flagged `_with_turn` as a homonym of `skills.py:_with_commit`, which means "a copy with X put in". I dropped it: it misses the python-naming bar. One `_with_` helper doesn't make an agreed convention. The same function prints "no open tasks with turn ROLE" in the filter sense, so the name reads as the code means it at its use.

### Design questions

None.

Summary: Standards 0. Spec 0. Behaviour 0. Smells 0. Names 0. None block and no design questions are open. Of the earlier findings, R1–R3 and R5–R8 are closed and R4 is deferred as a follow-up.

Verdict: approved
