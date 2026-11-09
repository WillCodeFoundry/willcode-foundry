# Plan: wcf-0033

## Approach
`task.py` gains a pure function, `next_task_id(taken_ids)`, that parses each id with the task id pattern, ignores
what doesn't match it, and returns the next id or raises `NoNextTaskIdError`. Because: DR1, a task's names are
spelled only in `task.py`. A read-only `ProjectTasks.taken_task_ids()` returns the names taken by task branches and
by the dirs under `OPEN_DIR` and `CLOSED_DIR` (one fetch of `agent-notes`). In the `foundry task create` command,
TASK becomes optional; when it is left out, a function `pick_next_task_id(project_tasks)` there returns
`next_task_id(project_tasks.taken_task_ids())`, adding "Give TASK…" to the refusal, and `create_main` then calls
`ProjectTasks.create_task` with that id, exactly as with a given TASK. `create_task` is unchanged by this task. A race
is lost at `create_task`'s own checks, as "already exists", or at its atomic push, as with two creates of one explicit
id today (AC7, OS5). Because: DR6, the entry point adds how to fix it. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.

Turned down: a `ProjectTasks.create_next_task` beside `create_task` (the approved plan until D2). The human chose one
create path, with the id picked at the entry point, at the cost of a second fetch of `agent-notes`. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.

## Steps
1. Refactor, no behaviour change: in `task.py`, a `BRANCH_PREFIX = "task/"` constant that `Task.branch` uses, and
   `_TASK_ID` with named groups `task_prefix` and `number`. Amended: R7. Because: a task id's own prefix is never
   called `prefix` alone, beside `BRANCH_PREFIX` (entry 7).
2. `task.py`: `NoNextTaskIdError(FoundryError)` and `next_task_id(taken_ids: Iterable[str]) -> str`. The task
   prefix is the one the most taken ids use, each id counted once (D1). The number is one more than the highest
   among that task prefix's ids only, formatted `{task_prefix}-{number:04d}`. Its locals are `task_prefix` and
   `task_prefixes`, never `prefix`. Unit tests first. Amended: R7. Because: entry 7.
3. `project_tasks.py`: `ProjectTasks.taken_task_ids() -> frozenset[str]`: the dir names under `OPEN_DIR` and
   `CLOSED_DIR` (none without `agent-notes`), plus each branch starting with `BRANCH_PREFIX`, with `BRANCH_PREFIX`
   cut off. It changes no file. `create_task` keeps its body as on the default branch. Amended: R7. Because: "prefix
   removed" read as the task id's prefix. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
4. `commands/task.py`: the shared `task_arguments` parent splits into a PROJECT parent and a TASK parent, so
   `create` takes TASK with `nargs="?"`. A module function `pick_next_task_id(project_tasks)` returns
   `next_task_id(project_tasks.taken_task_ids())` and re-raises `NoNextTaskIdError` with the hint; `create_main`
   calls it when TASK is left out, then `project_tasks.create_task(task_id, template)`. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
5. Docs, below.

## Names
- `next_task_id`, `NoNextTaskIdError`: "task id" from GLOSSARY.md; "next" from TASK.md's goal.
- `ProjectTasks.taken_task_ids`: TASK.md's "an id is taken". Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
- `BRANCH_PREFIX`: `task.py`'s constants are bare (`NOTES_BRANCH`, `OPEN_DIR`); "branch" is GLOSSARY.md's
  **Task branch**, `task/<id>`. The human kept it (entry 7), as long as the task id's part is always a task prefix.
- `pick_next_task_id` in `commands/task.py`: TASK.md's "picks the next task id"; `next_task_id` alone is `task.py`'s
  function, which it calls. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
- The regex groups `task_prefix` and `number`, and `next_task_id`'s locals `task_prefix` and `task_prefixes`: TASK.md's
  sharpened **Task id**, with whose prefix it is said every time. Amended: R7. Because: entry 7.

## Errors
- No task id taken (AC5):
  `error: the project repository has no task id to follow. Give TASK to say which task to create.`
- Prefixes tied for the most ids (AC6, as D1 changes it), the tied ones sorted and joined with ", ":
  `error: the project repository's task ids tie for the most common task prefix: abc, wcf. Give TASK to say which task to create.`
  Amended: R7. Because: entry 7 names the error text too.
  `NoNextTaskIdError` holds the text up to the first full stop; `commands/task.py` adds the second sentence.
- A lost race (AC7): git's own push rejection, as a `GitError`, printed by `cli.main` as `error: git -C … push … failed: …`;
  or, when the winner pushed before the loser's `create_task` read, its "task … already exists" refusal. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.

## Tests
- AC1: `tests/test_project_tasks.py`, `ProjectTasks.taken_task_ids` on `project_repository`, its seeded tasks
  removed and `wcf-0030` open, `wcf-0032` closed written with `edit_notes`, and `task/wcf-0033` made with
  `project_repository.git("branch", …)`, returns exactly those three ids and changes no ref. `tests/test_task_command.py`:
  the same repository through `cli.main(["task", "create", "store"])` with `enter_foundry` and `write_foundry`,
  asserting the two printed lines, exit 0, `head("task/wcf-0034") == head("main")`, the template under
  `.agent/tasks/open/wcf-0034/`, and the `agent-notes` commit subject `Add task wcf-0034`; the rest of "the same as
  `create PROJECT wcf-0034`" is `create_task`'s own tests, since it is the same call. Amended: R5. Because: AC1 says
  "the same as … would leave". Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
- AC2: `tests/test_project_tasks.py`, parametrized over `wcf-0007` open, closed, or branch-only beside an open
  `wcf-0003`: `next_task_id(taken_task_ids())` is `wcf-0008`. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
- AC3: `tests/test_task.py`, `next_task_id` parametrized: `wcf-0041` → `wcf-0042`, `wcf-9999` → `wcf-10000`,
  `wcf-00041` → `wcf-0042`; also `wcf-0001`, `wcf-0005` → `wcf-0006` (OS3).
- AC4: `tests/test_task.py`, `["wcf-0005", "spike", "WCF-0099"]` → `wcf-0006`; and `tests/test_project_tasks.py`,
  branches `task/spike` and `task/WCF-0099` beside `wcf-0005` give `wcf-0006`, through `taken_task_ids`. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
- AC5, AC6: `tests/test_task.py`, `next_task_id([])` and `next_task_id(["abc-0001", "wcf-0002"])` raise
  `NoNextTaskIdError` with the exact text. `tests/test_task_command.py`, parametrized: the CLI on a repository with
  no `agent-notes` and no task branch, and on one with branch-only `abc-0001` and closed `wcf-0002`, exits 1 with
  the exact stderr, and `git for-each-ref` is unchanged. Setup: for AC5, `project_repository.git("branch", "-D",
  "agent-notes")`, which leaves only `main`; for AC6, the seeded tasks' dirs removed with `edit_notes(remove=…)`,
  `wcf-0002`'s TASK.md written under `CLOSED_DIR` with `edit_notes`, and `task/abc-0001` made with
  `project_repository.git("branch", …)`. Amended: R6. Because: the seeded `tst-0000` and `cls-0000` would join the
  tie.
- The most common task prefix wins (D1): `tests/test_task.py`, `["wcf-0001", "wcf-0002", "sbx-0050"]` → `wcf-0003`,
  showing the other task prefix's higher number is ignored (Amended: R12. Because: bare "prefix" is under _Avoid_); and a three-way tie with one loser,
  `["abc-0001", "wcf-0002", "xyz-0003", "xyz-0004", "wcf-0005"]`, refuses naming only `wcf, xyz`.
  `tests/test_project_tasks.py`: the seeded `tst-0000` and `cls-0000` kept beside `wcf-0001` and `wcf-0002` give
  `wcf-0003`, through `taken_task_ids`. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
- Each id counted once (AC6): `tests/test_project_tasks.py`, open `wcf-0001` and `wcf-0002`, each with its task
  branch and notes as `create_task` leaves them, beside branch-only `sbx-0050`, `sbx-0051` and `sbx-0052` (seeded
  tasks removed): `next_task_id(taken_task_ids())` is `sbx-0053`. Counting a branch and its notes twice would give
  `wcf-0003`. `taken_task_ids` returns a set, and `next_task_id` also counts distinct ids, so a list with repeats is the same.
  Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
- AC7: `tests/test_task_command.py`. A `git` stand-in on PATH (`scripted_stand_in`) runs the real git, but before
  its first `push` runs a competing `python -m foundry.cli task create store` in the same foundry, with real git
  on PATH. The test's `cli.main(["task", "create", "store"])` exits 1 with a line starting `error: ` on stderr.
  The repository has one new task branch and one new `agent-notes` commit, and no second task notes dir. The
  stand-in writes the tips of `agent-notes` and of the new task branch to a file once the competitor finishes, and
  the test asserts both final tips equal them. Amended: R4. Because: the count alone can't tell whose commit
  survived. Setup: the seeded tasks' dirs removed with `edit_notes(remove=…)` and `wcf-0030` open written with
  `edit_notes`, so both creates pick `wcf-0031`. Amended: R10. Because: the seeded `tst-0000` and `cls-0000` tie,
  and both creates would refuse before any push.
- AC8: the existing create tests pass unchanged; the seeded repository already mixes the prefixes `tst` and `cls`,
  and `test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files` has no task at all.
- AC9: `tests/test_docs.py` passes unchanged.
- AC10: `tests/test_task_command.py`, `parse_args(["task", "create", "store"])` gives `task_id is None`, and
  `task create --help` (its SystemExit and captured stdout) shows `PROJECT [TASK]` and the default's help text.
- AC11: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov`, and mypy, vulture, pylint.

## Docs
- `README.md`: the command table's row becomes `foundry task create PROJECT [TASK]`, adding "Without TASK, the next
  task id: the task prefix most of the project's task ids use, and one more than the highest number taken with it.
  Ids with other task prefixes are ignored." The task id line says "a task prefix of lowercase ASCII letters, `-`,
  then a number of four or more digits". Amended: R1, R8, R9, R12. Because: entry 8 asks both texts to say other
  task prefixes are ignored; bare "prefix" is under _Avoid_.
- `GLOSSARY.md`: **Task id** as TASK.md's "Terms" sharpens it, but worded "made of a task prefix of lowercase ASCII
  letters, `-`, then a number of four or more digits", so the definition itself never says bare "prefix", with
  "prefix (alone, for a task id's letters)" under its _Avoid_. Amended: R7, R9. Because: the human asked for the rule
  there (entry 7), and the definition must keep it.
- `ARCHITECTURE.md`: `project_tasks.py`'s codemap row says "creating them, under an id given or the next one";
  `task.py`'s row (`ARCHITECTURE.md:29`) adds "and `next_task_id`, which picks the next task id from the taken
  ones". Amended: R2. Because: the codemap is where a reader looks for it.
- Docstrings: `project_tasks.py`'s module, where "callers pass task ids. Listing is the exception: it reads every
  dir under OPEN_DIR from one fetch" (`:5-6`) adds `taken_task_ids` as a second exception, which takes no id and
  reads the dirs under `OPEN_DIR` and `CLOSED_DIR` from one fetch of `NOTES_BRANCH`, and the task branches from the
  remote's branch list, Amended: R3, R11. Because: the sentence becomes untrue otherwise, and the branches come from
  `git ls-remote --heads`, not the fetch, Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.; `task.py`'s module docstring (`:1`), "what a task's names are, how the next
  task id is picked, and the task template", Amended: R2; `task.py`'s `_TASK_ID` comment; the `create` parser's
  TASK help, "task id, e.g. wcf-0042 (default: the next id with the task prefix most of the project's task ids
  use; ids with other task prefixes are ignored)". Amended: R1, R8, R12. Because: entry 8; bare "prefix" is under
  _Avoid_.
