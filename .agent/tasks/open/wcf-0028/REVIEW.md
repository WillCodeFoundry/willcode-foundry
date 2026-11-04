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

## Round 3 (reviewing 294b4af)

The code hasn't changed since round 2. After round 2, the human read `_open_task_in_dir` and asked for it to be fixed before the PR, so this round reopens the review with one finding. `TASK.md` is unchanged: this round reviews against `e3b591a`, as rounds 1 and 2 did.

### Earlier findings

Unchanged from round 2: R4 is deferred, and every other finding is closed.

### Smells

**R9 · Blocking · possible Duplicated Code: `_open_task_in_dir` reworks a check that `Task` already makes** (`src/foundry/project_tasks.py:158-169`)
- The lowercasing lives only in `Task.from_id_and_status` (`src/foundry/task.py:67-70`), which `as_open` calls; it tidies ids people type. The plain constructor checks the id exactly as given: `__post_init__` (`task.py:59-64`) matches it against `_TASK_ID`, which has no upper case.
- `_open_task_in_dir` builds the task with `as_open`, which lowercases the dir name. It then compares `task.id != dir_name` to catch the case it just lowercased, and writes its own "upper case letters are not allowed" reason. So the function has two ways to fail and two reasons to give where one would do.
- A dir name is never typed by a person, so nothing needs lowercasing. Built with `Task(dir_name, Status.OPEN)`, the task has only `Task`'s own check, and its own reason.
- The function still has a job: the message. On its own, `Task`'s error doesn't say the problem is a dir under `OPEN_DIR` on `agent-notes`, or that the fix is to rename or remove it, and TASK.md asks that the message say how to fix it. What's left is the path, the fix, and catching `Task`'s error.
- `Task`'s message (`task.py:62`) says "use letters, digits, '.', '_' and '-'". For `WCF-1` that misleads, because upper-case letters are letters too. Saying lowercase letters there fixes the listing's message and `create`'s.
- Who hits it: the next dev who changes the id rules, who has to keep `_TASK_ID` and this comparison in step. Also anyone who lists a project with an upper-case dir, or runs `create` with a bad id, and is told letters are allowed.
- Direction: build the task with the constructor, keep only the path and the fix in `_open_task_in_dir`, and say lowercase in `Task`'s message. Keep the `Bad Dir` and `WCF-1` tests passing, and pin the new wording.

### Standards, Spec, Behaviour, Names

No new findings.

### Design questions

None.

Summary: Smells 1 (1 blocking; R9, `_open_task_in_dir` reworks `Task`'s own check). Standards, Spec, Behaviour, Names 0. No design questions open.

Verdict: changes needed

## Round 4 (reviewing 7008206)

This round reviews the fix diff `294b4af..7008206`, against `TASK.md` at `e3b591a`. That version is unchanged since rounds 1 to 3, and it was written by an allowed commit. `e3b591a` is signed by the planner's identity, which the architect shares (see `allowed_signers`), so it can't be told apart from an architect commit. No other role changed `TASK.md`, and the task has no `DESIGN.md`.

The fix diff contains these commits:
- da1c3b8: the R9 fix.
- 17606fe and 94ace56: 17606fe removed the helper, and 94ace56 reverts that, at the human's request. The two cancel out.
- 7008206: renames the helper `_open_task_in_dir` to `_open_task_for_dir`, the human's choice.

The rest of `294b4af..HEAD` is the default branch merged in 3b6ff1e (#44, role models). It isn't part of this task's diff, so this round doesn't review it. Host tier, ruff and mypy pass on 7008206.

### Earlier findings

- **R9: closed.** `_open_task_for_dir` (`src/foundry/project_tasks.py:158-164`) builds `Task(dir_name, Status.OPEN)`. That leaves `Task`'s own check as the only one, and the wrapper adds only the path, the fix and the chained error. `Task`'s message says "use lowercase letters" (`src/foundry/task.py:62`). The wording is pinned by `test_an_invalid_task_id_is_told_letters_must_be_lowercase` (`tests/test_task.py:154`), and through the wrapper by the `WCF-1` test (`tests/test_task.py:644-652`). The `Bad Dir` test still passes.
- R1–R3 and R5–R8 stay closed. R4 stays deferred.

### Standards

**R10 · Follow-up · the comment on `_TASK_ID` says ids are "Matched after lowercasing"** (`src/foundry/task.py:31-33`)
- That was true while every caller went through `from_id_and_status`. Since da1c3b8, `_open_task_for_dir` calls the constructor directly, and it relies on the pattern *not* lowercasing to refuse an upper-case dir.
- AGENTS.md "Writing" asks every comment to state its point accurately, and this one now contradicts a caller.
- Who hits it: someone changing the id pattern, rarely. If they trusted the comment and added `A-Z`, `test_an_upper_case_dir_is_not_a_task_id_either` would fail first. So the finding misses the Blocking bar.
- Direction: say that `from_id_and_status` lowercases and the constructor checks the id as given.

No other findings. Design rules 1, 3 and 6 hold for the fix.

### Spec

No new findings. The wrapper's message names the dir and says how to fix it, as TASK.md asks. Both tests pin it.

### Behaviour

No new findings. Reproduced in a throwaway clone:
- Each of these dirs fails its project with a message that names it and ends "Rename or remove it.": `WCF-1`, `Wcf-1`, `wcf-1.lock`, `a..b`, `é-1`, `-x`.
- Valid dirs still list in id order.
- Where people type an id (`create`, `close`, `reopen`), the id is lowercased before the check. So the new wording shows only for an id that is invalid for some other reason, and following it gives a valid id.

### Smells

| Function | Verdict |
|---|---|
| `project_tasks.py:ProjectTasks.list_open_task_summaries` | clean (only the call's name changed) |
| `project_tasks.py:_open_task_for_dir` | clean; simpler than at 294b4af, one try/except, one reason; R9 closed |
| `task.py:Task.__post_init__` | clean (wording only) |
| `tests/test_task.py:test_an_invalid_task_id_is_told_letters_must_be_lowercase` | new, clean |
| `tests/test_task.py:test_an_upper_case_dir_is_not_a_task_id_either` | clean |

No new findings. The one-caller wrapper stays, at the human's request (entry 13), and it adds the path and the fix of its own.

### Names

All clean:
- `_open_task_for_dir` (renamed from `_open_task_in_dir`): a noun phrase for a pure function, like `_turn_of`. No homonym found.
- `test_an_invalid_task_id_is_told_letters_must_be_lowercase`
- `error`: the codebase's usual name for a caught exception.
- the message's "lowercase": the glossary's word, from **Task id**.
- the docstring's prose: no new term.

No new findings.

### Design questions

None.

Summary: Standards 1 (Follow-up; R10, a stale comment on `_TASK_ID`). Spec, Behaviour, Smells and Names 0. Nothing blocks, and no design questions are open. R9 is closed, R4 is deferred and R10 is a follow-up.

Verdict: approved

## Round 5 (reviewing 7008206)

At the human's request, after round 4's approval. The code is unchanged since round 4. This round reviews it again for names, and for the smell behind one of them.

TASK.md: unchanged since e3b591a, which is allowed (signed by the planner's identity, which the architect shares). No other commits touch it. No DESIGN.md.

**The human's decision (LOG.md entry 18):** the scope constraint is relaxed. TASK.md's out-of-scope line "Changing `ProjectClone.read`, `read_task_turn` or `in_scratch_clone`" no longer holds. Any change that makes the code simpler and easier to read is in scope. The human chose the names in R11–R14.

The role allows at most three rounds before `no-agreement`. This round and its `changes-needed` outcome go past that only because the human asked for them. The dev and the reviewer don't disagree about anything.

### Earlier findings

- R1–R3, R5–R9: closed.
- R4 (multi-line `TURN`): deferred, unchanged.
- R10 (the stale comment on `_TASK_ID`, `task.py:31-33`): **still open**. The dev deferred it to avoid a commit after the approval, and that reason no longer applies. Fix it in this PR: the comment should say the pattern is matched as given, and that `Task.as_open` and `Task.from_id_and_status` lowercase the id before it.

### New findings

**R11 · Blocking · Names.** `ProjectClone._local_ref` (`project_clone.py:177`) returns `refs/remotes/origin/<branch>`, a remote-tracking ref. In git, "local" means `refs/heads`. At its use in `push_atomic` (`:163`) the name reads backwards: the `from_remote` refspecs use `_local_ref`, while the `from_local` ones use `refs/heads`. Rename it to `_tracking_ref` (the human's choice). Also, with a `path` it returns `<ref>:<path>`, an object spec, not a ref. The dev can split that out, or document it in a docstring.

**R12 · Blocking · Names.** `local_list_dir` and `local_read` (`project_clone.py:85,102`): "local" is ambiguous in a class whose `exists` reads the checked-out files, while these read the fetched tracking ref. Rename them to `fetched_list_dir` and `fetched_read` (the human's choice). Rename the tests that use them as well (`test_local_list_dir_…`, `test_local_read_…`, `test_local_reads_of_an_unfetched_branch_…`), and the section comment at `tests/test_task.py:323`.

**R13 · Blocking · Names.** `list_projects` (`commands/task.py:134`): in this module "list" is the command's verb, printing tasks, but this function only picks the projects to list. NAMES.md notes it is one letter from `list_project`. Rename it to `chosen_projects` (the human's choice), and rename `test_list_projects_…` with it.

**R14 · Blocking · Names.** `MissingPathError` (`project_clone.py:13`) is also raised when the path exists but is the wrong kind, such as a dir where a file is wanted. Its own docstring has to say so. Rename it to `NotOnBranchError` (the human's choice): the dir or file asked for isn't on the branch. The messages already read that way ("agent-notes has no file …").

**R15 · Blocking · Smells.** There are two ways to read a file from `agent-notes`, and `_turn_of` (`project_tasks.py:167`) is the adapter between them:

| | `ProjectClone.read` | `local_read` (R12: `fetched_read`) |
|---|---|---|
| fetches | on every call | never |
| missing file | returns `None` | raises `MissingPathError` (R14: `NotOnBranchError`) |
| path is a dir | returns `git show`'s listing of the tree as text | raises |

`_turn_of` takes `text: str | None` only so that both can feed it. `_read_local_task_summary` (`:137`) catches the precise error only to turn it back into `None`. A pre-existing bug comes with it: `read` checks only `cat-file -e`, so a dir at `TURN` makes `read_task_turn` return the tree listing as the turn.

`read_task_turn` (`:115`) is `read`'s only caller. `get_task_by_id` has already fetched `NOTES_BRANCH`, through `check_out`, by the time it returns. Fix:
- Make `read_task_turn` read through `fetched_read`, like listing does.
- Delete `ProjectClone.read`.
- Replace `_turn_of` and `_read_local_task_summary` with one method. It takes a `Task` and `fix`, reads `TURN_FILE` with `fetched_read`, and raises the shared `FoundryError` for a file that is missing, not a file, or blank. Its name is a verb, since it reads git, and must not be one underscore from `read_task_turn`. Something like `_read_fetched_turn(task, *, fix)`; the dev decides and records it in NAMES.md.
- `list_open_task_summaries` then builds `TaskSummary(task, self._read_fetched_turn(task, fix=...))` directly.
- Add a test: a dir at `TURN` makes `read_task_turn` raise. Update the docstrings that mention `read` (`fetch_branch`'s, and `project_tasks.py`'s module docstring if it does).

This also takes one fetch off `read_task_turn`, and with it off every `foundry run`. Spell no path again (design rule 1).

### Suggested follow-up (not this PR)

- `_require_command` (`agent_runtime/hardening.py:207`) returns a value, but the other `_require_*` functions (`_require_fetched`, `_require_log_only_added_to`) only guard and return `None`. The human prefers "require" to mean "check, or raise". Unrelated to this task.

Summary: Names 4 (R11–R14), Smells 1 (R15), Standards 1 still open (R10). All Blocking, at the human's request. No design questions.

Verdict: changes needed

## Round 6 (reviewing 84971e7)

This round reviews the fixes since round 5 (7008206..84971e7). That includes merge 46b7d16 of origin/main (wcf-0029), and the refactors the human asked for in LOG.md entries 20–29. Only lines that are also in the task's full diff (`a781f1d...84971e7`) count as new surface.

TASK.md: unchanged since e3b591a. That commit is allowed: it is signed by the planner's identity, which the architect shares. No other commit touches it. There is no DESIGN.md.

The departures from TASK.md's Context are the human's, and this round doesn't judge them: `ProjectClone.read` removed (round 5), filtering in `filter_project_listing`, `_require_on_branch`, and `read_listings_and_errors` (D1, entry 29).

### Earlier findings

- R10: **closed**. The merge replaced the comment with main's. It now states the pattern as matched (`task.py:31-32`).
- R11: **closed**. `_tracking_ref` returns only the ref, and every caller uses it.
- R12: **closed**. `fetched_list_dir` and `fetched_read` are used in the code, the tests, the section comment (`tests/test_task.py:356`) and `fetch_branch`'s docstring.
- R13: **closed**. `chosen_projects` is used in the code and in its test.
- R14: **closed**. `NotOnBranchError`'s docstring names the wrong-kind case.
- R15: **closed**. There is one turn reader now, `_read_fetched_turn` (`project_tasks.py:140`). `ProjectClone.read`, `_turn_of` and `_read_local_task_summary` are gone. `test_a_dir_at_turn_is_no_turn` pins the bug that came with them. A closed task's turn still reads, and an unknown id raises before anything is read.
- R4: deferred, unchanged.

### Standards

R10–R15 are closed for this axis: no docstring or comment names a removed function.

**R18 · Follow-up.** In `list_main`, the `--turn` filter is wired at `commands/task.py:99`, and no test reaches that call.
- Design rule 7 says "Logic in `main` is logic no test reaches."
- The end-to-end test (`tests/test_task.py:830`) never passes `--turn`.
- Who hits it: a dev who mis-wires `args.turn` would ship a `--turn` that does nothing, and no test would fail.
- It is only a Follow-up because the human chose this placement (entry 26), and the step is one comprehension.
- Direction: add a `--turn` call to the end-to-end test.

**R19 · Follow-up.** The `ProjectClone` class docstring is stale (`project_clone.py:22-23`).
- It says the clone holds "nothing until a branch is checked out". But `fetch_branch` now makes a branch readable by `fetched_read` and `fetched_list_dir` with no checkout.
- Who hits it: a reader of the class docstring alone. The method docstrings say otherwise, so the cost is low.
- Direction: reword it to cover fetching without a checkout.

**R20 · Follow-up.** Three docstrings chain reasons behind colons, which AGENTS.md "Writing" rules out: `commands/task.py:151-152` (a sentence of about 33 words), `commands/task.py:164-165` and `project_clone.py:17-18`. Nobody would be misled by them. Direction: split each into short sentences.

Design rules 1, 3 and 6 hold for the fixes. The README rows and ARCHITECTURE.md's codemap rows still match the code.

### Spec

R15 is closed: `test_a_dir_at_turn_is_no_turn` (`tests/test_task.py:440`) shows it.

The reviewer reproduced both findings below: with the code changed as each describes, every test in `tests/test_task.py` still passes. Both gaps were already there at 7008206, but 84971e7 rewrote these lines (it moved the catch into `read_listings_and_errors`, and changed the width line), so they are this round's surface.

**R16 · Blocking.** No test shows that a project failing with a `FoundryError` lets the rest be listed (`commands/task.py:158`).
- Spec: "A project is a failure, and nothing of it is listed, when any of these holds: … no `agent-notes` branch; an open task's `TURN` is missing, empty or not a file; a directory under `.agent/tasks/open/` is not a valid task id. It prints `error: PROJECT: <message>` on stderr, the remaining projects are still listed."
- Both tests that go through the catch, `test_each_project_gives_a_listing_or_an_error_naming_it` (`:819`) and the end-to-end test (`:830`), use an unreachable repository, which raises `GitError`.
- Narrowing the catch to `except GitError` passes every test. Yet with that change, a missing `TURN`, a bad dir name or a missing `agent-notes` would reach `cli.main` without the project's name, and the remaining projects would go unlisted.
- c475eca dropped the earlier test of this layer, and that test used an unreachable repository too.
- Direction: in `:819`, make one project fail with a `FoundryError`, such as a task with no `TURN`.

**R17 · Blocking.** No test pins "the widths taken across all the task lines printed" for the project column (`commands/task.py:181`).
- Spec: "in aligned columns two spaces apart, the widths taken across all the task lines printed."
- Counting every project's name, including those with no task line, passes every test. In `test_a_project_without_tasks_is_a_line_outside_the_columns` (`tests/test_task.py:774`), `empty` and `store` are the same length.
- Who hits it: anyone listing with `--turn`, or a project with a long name and no open tasks. A regression would pad every task line, and no test would fail.
- Direction: give the no-tasks project in `:774` a name longer than the project with tasks.

Everything else is shown: the error line and exit codes (`:819-851`), the two no-tasks lines (`:774`, `:780`), one fetch per project (`:720`), and the parser with an unknown project (`:798-816`). The reviewer also checked read-only use by hand: with no signing key, listing works and no ref in origin changes. Nothing goes beyond TASK.md, apart from the human's departures.

### Behaviour

R15 is closed. Reproduced against real repositories in a throwaway clone:
- `read_task_turn` raises the shared message for a dir, a missing file or a blank `TURN`.
- A symlinked `TURN` reads as its target's name.
- A closed task's turn still reads.
- An unknown id, or a repository with no `agent-notes`, raises `TaskNotFoundError` before `fetched_read` runs.

Every suspect checked came back clean:
- `_require_on_branch` matches nested paths exactly, since `ls-tree -z` gives full, unquoted paths.
- `list_open_task_summaries` behaves as TASK.md says in every case.
- An unreachable repository becomes a `FoundryError` naming the project, and the other projects still list.
- `filter_project_listing` and `listing_lines` give the right notes and widths for plain values.
- `list_main` returns 1 exactly when there are stderr lines.
- `chosen_projects` refuses an unknown name before any clone is made.

No new findings. The host tier, ruff and mypy pass at 84971e7.

### Smells

| Function | Verdict |
|---|---|
| `commands/task.py:list_main` | clean |
| `commands/task.py:ProjectListing` | R22 |
| `commands/task.py:chosen_projects` | clean (rename only) |
| `commands/task.py:read_project_listing` | clean; simpler without its try |
| `commands/task.py:read_listings_and_errors` | new, clean |
| `commands/task.py:filter_project_listing` | new, R22 |
| `commands/task.py:listing_lines` | clean; flatter than before |
| `project_clone.py:NotOnBranchError`, `fetch_branch`, `fetched_list_dir`, `fetched_read`, `push_atomic`, `_require_fetched`, `_tracking_ref` | clean; `fetched_list_dir` simpler |
| `project_clone.py:_require_on_branch`, `_ls_tree` | new, clean |
| `project_tasks.py:read_task_turn`, `list_open_task_summaries` | clean |
| `project_tasks.py:_read_fetched_turn` | new, clean; R15 closed |
| `tests/test_task.py`: the `fetched_*` tests, listing tests, line and filter tests, `test_chosen_projects_*`, `test_each_project_gives_a_listing_or_an_error_naming_it` | clean, except R21 |
| `tests/test_task.py:test_a_dir_at_turn_is_no_turn` | new, R21 |

**R21 · Follow-up · possible Duplicated Code.** Three test fixtures clone `agent-notes`, write, commit and push:
- `push_notes` (`tests/test_task.py:511`), already there at the fixed point;
- `edit_notes` (`:626`), which this task added;
- the steps inline in `test_fetched_read_reads_a_file_and_a_link_as_its_target_name` (`:399-404`), which `edit_notes(symlink=...)` already covers.

The new `test_a_dir_at_turn_is_no_turn` uses `push_notes`, while its twin listing test uses `edit_notes`. Who hits it: the next dev who adds a notes fixture has to choose between the two. Direction: have `:399-404` call `edit_notes`.

**R22 · Follow-up, accept as is · possible Divergent Change.** The no-tasks wording is split between `ProjectListing`'s default (`commands/task.py:131`) and `filter_project_listing` (`:171`), and neither is the line formatter. This follows from the human's split of filtering from printing, and the only local alternative brings back the coupling the split removed.

### Names

Clean:
- the human's choices: `_tracking_ref`, `fetched_list_dir`, `fetched_read`, `chosen_projects`, `NotOnBranchError`, `filter_project_listing`. Each is applied everywhere.
- the new identifiers: `_require_on_branch`, `_ls_tree`, `_ENTRY_KIND`, `entry_type` (git's word), `ProjectListing`, `no_tasks_note`, `read_project_listing`, `read_listings_and_errors`, `listing_lines`, `_read_fetched_turn`, `fix`, `errors`, `kept`.
- the new test names.

No removed name is left in the repository: `MissingPathError`, `local_read`, `list_projects`, `ProjectFailure`, `with_turn`, `_turn_of` and `_object_type` all return nothing. The added prose keeps the glossary's words. R11–R14 are closed.

**R23 · Follow-up.** NAMES.md still names removed code:
- The `no_tasks_note` row says it is "set by `with_turn`".
- The `_open_task_in_dir` rows justify the name "as `_turn_of` is".
- There is a "removed" row for `ProjectFailure`.

Who hits it: the next dev or reviewer who reads NAMES.md for a name's reasons. The python-naming skill says to keep its rows current. Direction: name `filter_project_listing` in the `no_tasks_note` row, and drop the rows for names the code no longer has.

### Design questions

None.

Summary: Standards 3 (Follow-ups R18–R20; worst is R18, `--turn` untested where `main` wires it). Spec 2, both Blocking (R16, the `FoundryError` half of the per-project catch is untested; R17, the name width is unpinned). Behaviour 0. Smells 2 (Follow-ups R21 and R22; R22 accepted as is). Names 1 (Follow-up R23, stale NAMES.md rows). R10–R15 are closed and R4 is deferred. No design questions are open.

Verdict: changes needed
