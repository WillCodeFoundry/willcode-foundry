# Plan: wcf-0033

## Approach
`task.py` gains a pure function, `next_task_id(taken_ids)`, that parses each id with the task id pattern, ignores
what doesn't match it, and returns the next id or raises `NoNextTaskIdError`. Because: DR1, a task's names are
spelled only in `task.py`. `ProjectTasks.create_next_task(task_template)` gathers the taken ids from the same reads
`create_task` already makes (the remote's branches and one fetch of `agent-notes`), picks the id, and goes on exactly
as `create_task` does, writing on what it read. A race is then lost at the atomic push, as with two creates of one
explicit id today (AC7, OS5). In the `foundry task create` command, TASK becomes optional, and a function
`create_task` there chooses between the two methods and adds "Give TASK…" to the refusal. Because: DR6, the entry
point adds how to fix it; DR7, `create_main` only builds and passes.

Turned down: a `task_id: str | None` on `ProjectTasks.create_task`. A separate method keeps today's create, with
TASK, word for word (AC8), and names the new behaviour at its call. Turned down too: reading the taken ids in a
fetch of their own before `create_task`. It would fetch `agent-notes` twice and widen the race window.

## Steps
1. Refactor, no behaviour change: in `task.py`, a `BRANCH_PREFIX = "task/"` constant that `Task.branch` uses, and
   `_TASK_ID` with named groups `task_prefix` and `number`. Amended: R7. Because: a task id's own prefix is never
   called `prefix` alone, beside `BRANCH_PREFIX` (entry 7).
2. `task.py`: `NoNextTaskIdError(FoundryError)` and `next_task_id(taken_ids: Iterable[str]) -> str`. The task
   prefix is the one the most taken ids use, each id counted once (D1). The number is one more than the highest
   among that task prefix's ids only, formatted `{task_prefix}-{number:04d}`. Its locals are `task_prefix` and
   `task_prefixes`, never `prefix`. Unit tests first. Amended: R7. Because: entry 7.
3. `project_tasks.py`: move `create_task`'s body into `_create(task_template, *, task_id: str | None)`, which, given
   None, takes `next_task_id` of `_taken_task_ids(branches, notes_branch)` after reading and before any check.
   `create_task` and `create_next_task` each call it. `_taken_task_ids` is the dir names under `OPEN_DIR` and
   `CLOSED_DIR` (none without `agent-notes`), plus each branch starting with `BRANCH_PREFIX`, with `BRANCH_PREFIX`
   cut off. Amended: R7. Because: "prefix removed" read as the task id's prefix.
4. `commands/task.py`: the shared `task_arguments` parent splits into a PROJECT parent and a TASK parent, so
   `create` takes TASK with `nargs="?"`. A module function `create_task(project_tasks, task_id, task_template)`
   calls `create_next_task` when `task_id` is None and re-raises `NoNextTaskIdError` with the hint; `create_main`
   calls it.
5. Docs, below.

## Names
- `next_task_id`, `NoNextTaskIdError`: "task id" from GLOSSARY.md; "next" from TASK.md's goal.
- `ProjectTasks.create_next_task`: beside `create_task`, the word it already uses.
- `BRANCH_PREFIX`: `task.py`'s constants are bare (`NOTES_BRANCH`, `OPEN_DIR`); "branch" is GLOSSARY.md's
  **Task branch**, `task/<id>`. The human kept it (entry 7), as long as the task id's part is always a task prefix.
- `create_task` in `commands/task.py`: the same act as the method it calls, so the same word.
- The regex groups `task_prefix` and `number`, and `next_task_id`'s locals `task_prefix` and `task_prefixes`: TASK.md's
  sharpened **Task id**, with whose prefix it is said every time. Amended: R7. Because: entry 7.

## Errors
- No task id taken (AC5):
  `error: the project repository has no task id to follow. Give TASK to say which task to create.`
- Prefixes tied for the most ids (AC6, as D1 changes it), the tied ones sorted and joined with ", ":
  `error: the project repository's task ids tie for the most common task prefix: abc, wcf. Give TASK to say which task to create.`
  Amended: R7. Because: entry 7 names the error text too.
  `NoNextTaskIdError` holds the text up to the first full stop; `commands/task.py` adds the second sentence.
- A lost race (AC7): git's own push rejection, as a `GitError`, printed by `cli.main` as `error: git -C … push … failed: …`.

## Tests
- AC1: `tests/test_project_tasks.py`, `ProjectTasks.create_next_task` on `project_repository`, its seeded tasks
  removed and `wcf-0030` open, `wcf-0032` closed written with `edit_notes`, and `task/wcf-0033` made with
  `project_repository.git("branch", …)`. Asserts `Task.as_open("wcf-0034")`, `head("task/wcf-0034") == head("main")`,
  the template under `.agent/tasks/open/wcf-0034/`, one new signed commit. `tests/test_task_command.py`: the same
  repository through `cli.main(["task", "create", "store"])` with `enter_foundry` and `write_foundry`, asserting the
  two printed lines and exit 0. The method test also asserts the new `agent-notes` commit's subject,
  `Add task wcf-0034`. Amended: R5. Because: AC1 says "the same as … would leave".
- AC2: `tests/test_project_tasks.py`, parametrized over `wcf-0007` open, closed, or branch-only beside an open
  `wcf-0003`: `create_next_task` returns `wcf-0008`.
- AC3: `tests/test_task.py`, `next_task_id` parametrized: `wcf-0041` → `wcf-0042`, `wcf-9999` → `wcf-10000`,
  `wcf-00041` → `wcf-0042`; also `wcf-0001`, `wcf-0005` → `wcf-0006` (OS3).
- AC4: `tests/test_task.py`, `["wcf-0005", "spike", "WCF-0099"]` → `wcf-0006`; and `tests/test_project_tasks.py`,
  branches `task/spike` and `task/WCF-0099` beside `wcf-0005` give `wcf-0006`.
- AC5, AC6: `tests/test_task.py`, `next_task_id([])` and `next_task_id(["abc-0001", "wcf-0002"])` raise
  `NoNextTaskIdError` with the exact text. `tests/test_task_command.py`, parametrized: the CLI on a repository with
  no `agent-notes` and no task branch, and on one with branch-only `abc-0001` and closed `wcf-0002`, exits 1 with
  the exact stderr, and `git for-each-ref` is unchanged. Setup: for AC5, `project_repository.git("branch", "-D",
  "agent-notes")`, which leaves only `main`; for AC6, the seeded tasks' dirs removed with `edit_notes(remove=…)`,
  `wcf-0002`'s TASK.md written under `CLOSED_DIR` with `edit_notes`, and `task/abc-0001` made with
  `project_repository.git("branch", …)`. Amended: R6. Because: the seeded `tst-0000` and `cls-0000` would join the
  tie.
- The most common prefix wins (D1): `tests/test_task.py`, `["wcf-0001", "wcf-0002", "sbx-0050"]` → `wcf-0003`,
  showing the other prefix's higher number is ignored; and a three-way tie with one loser,
  `["abc-0001", "wcf-0002", "xyz-0003", "xyz-0004", "wcf-0005"]`, refuses naming only `wcf, xyz`.
  `tests/test_project_tasks.py`: the seeded `tst-0000` and `cls-0000` kept beside `wcf-0001` and `wcf-0002` give
  `wcf-0003`.
- Each id counted once (AC6): `tests/test_project_tasks.py`, open `wcf-0001` and `wcf-0002`, each with its task
  branch and notes as `create_task` leaves them, beside branch-only `sbx-0050`, `sbx-0051` and `sbx-0052` (seeded
  tasks removed): `create_next_task` returns `sbx-0053`. Counting a branch and its notes twice would give `wcf-0003`.
  `_taken_task_ids` returns a set, and `next_task_id` also counts distinct ids, so a list with repeats is the same.
- AC7: `tests/test_task_command.py`. A `git` stand-in on PATH (`scripted_stand_in`) runs the real git, but before
  its first `push` runs a competing `python -m foundry.cli task create store` in the same foundry, with real git
  on PATH. The test's `cli.main(["task", "create", "store"])` exits 1 with a line starting `error: ` on stderr.
  The repository has one new task branch and one new `agent-notes` commit, and no second task notes dir. The
  stand-in writes the tips of `agent-notes` and of the new task branch to a file once the competitor finishes, and
  the test asserts both final tips equal them. Amended: R4. Because: the count alone can't tell whose commit
  survived.
- AC8: the existing create tests pass unchanged; the seeded repository already mixes the prefixes `tst` and `cls`,
  and `test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files` has no task at all.
- AC9: `tests/test_docs.py` passes unchanged.
- AC10: `tests/test_task_command.py`, `parse_args(["task", "create", "store"])` gives `task_id is None`, and
  `task create --help` (its SystemExit and captured stdout) shows `PROJECT [TASK]` and the default's help text.
- AC11: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov`, and mypy, vulture, pylint.

## Docs
- `README.md`: the command table's row becomes `foundry task create PROJECT [TASK]`, adding "Without TASK, the next
  task id: the task prefix most of the project's task ids use, and one more than the highest number taken with it.
  Ids with other prefixes are ignored." The task id line says "a prefix of lowercase ASCII letters, `-`, then a
  number of four or more digits". Amended: R1, R8. Because: entry 8 asks both texts to say other prefixes are
  ignored.
- `GLOSSARY.md`: **Task id** as TASK.md's "Terms" sharpens it, calling its letters the **task prefix**, with
  "prefix (alone, for a task id's letters)" under its _Avoid_. Amended: R7. Because: the human asked for the rule
  there (entry 7).
- `ARCHITECTURE.md`: `project_tasks.py`'s codemap row says "creating them, under an id given or the next one";
  `task.py`'s row (`ARCHITECTURE.md:29`) adds "and `next_task_id`, which picks the next task id from the taken
  ones". Amended: R2. Because: the codemap is where a reader looks for it.
- Docstrings: `project_tasks.py`'s module, where "callers pass task ids. Listing is the exception: it reads every
  dir under OPEN_DIR from one fetch" (`:5-6`) adds `create_next_task` as a second exception, which takes no id and
  reads `OPEN_DIR` and `CLOSED_DIR` and the task branches from one fetch, Amended: R3. Because: the sentence becomes
  untrue otherwise; `create_task`'s; `task.py`'s module docstring (`:1`), "what a task's names are, how the next
  task id is picked, and the task template", Amended: R2; `task.py`'s `_TASK_ID` comment; the `create` parser's
  TASK help, "task id, e.g. wcf-0042 (default: the next id with the task prefix most of the project's task ids
  use; ids with other prefixes are ignored)". Amended: R1, R8. Because: entry 8.
