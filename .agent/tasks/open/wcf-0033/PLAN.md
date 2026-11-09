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
   `_TASK_ID` with named groups `prefix` and `number`.
2. `task.py`: `NoNextTaskIdError(FoundryError)` and `next_task_id(taken_ids: Iterable[str]) -> str`. The number is
   one more than the highest, formatted `{prefix}-{number:04d}`. Unit tests first.
3. `project_tasks.py`: move `create_task`'s body into `_create(task_template, *, task_id: str | None)`, which, given
   None, takes `next_task_id` of `_taken_task_ids(branches, notes_branch)` after reading and before any check.
   `create_task` and `create_next_task` each call it. `_taken_task_ids` is the dir names under `OPEN_DIR` and
   `CLOSED_DIR` (none without `agent-notes`), plus each branch starting with `BRANCH_PREFIX`, prefix removed.
4. `commands/task.py`: the shared `task_arguments` parent splits into a PROJECT parent and a TASK parent, so
   `create` takes TASK with `nargs="?"`. A module function `create_task(project_tasks, task_id, task_template)`
   calls `create_next_task` when `task_id` is None and re-raises `NoNextTaskIdError` with the hint; `create_main`
   calls it.
5. Docs, below.

## Names
- `next_task_id`, `NoNextTaskIdError`: "task id" from GLOSSARY.md; "next" from TASK.md's goal.
- `ProjectTasks.create_next_task`: beside `create_task`, the word it already uses.
- `BRANCH_PREFIX`: `task.py`'s constants are bare (`NOTES_BRANCH`, `OPEN_DIR`); "branch" is GLOSSARY.md's
  **Task branch**, `task/<id>`.
- `create_task` in `commands/task.py`: the same act as the method it calls, so the same word.
- The regex groups `prefix` and `number`: TASK.md's sharpened **Task id**.

## Errors
- No task id taken (AC5):
  `error: the project repository has no task id to follow. Give TASK to say which task to create.`
- Several prefixes (AC6), prefixes sorted and joined with ", ":
  `error: the project repository's task ids use more than one prefix: abc, wcf. Give TASK to say which task to create.`
  `NoNextTaskIdError` holds the text up to the first full stop; `commands/task.py` adds the second sentence.
- A lost race (AC7): git's own push rejection, as a `GitError`, printed by `cli.main` as `error: git -C … push … failed: …`.

## Tests
- AC1: `tests/test_project_tasks.py`, `ProjectTasks.create_next_task` on `project_repository`, its seeded tasks
  removed and `wcf-0030` open, `wcf-0032` closed written with `edit_notes`, and `task/wcf-0033` made with
  `project_repository.git("branch", …)`. Asserts `Task.as_open("wcf-0034")`, `head("task/wcf-0034") == head("main")`,
  the template under `.agent/tasks/open/wcf-0034/`, one new signed commit. `tests/test_task_command.py`: the same
  repository through `cli.main(["task", "create", "store"])` with `enter_foundry` and `write_foundry`, asserting the
  two printed lines and exit 0.
- AC2: `tests/test_project_tasks.py`, parametrized over `wcf-0007` open, closed, or branch-only beside an open
  `wcf-0003`: `create_next_task` returns `wcf-0008`.
- AC3: `tests/test_task.py`, `next_task_id` parametrized: `wcf-0041` → `wcf-0042`, `wcf-9999` → `wcf-10000`,
  `wcf-00041` → `wcf-0042`; also `wcf-0001`, `wcf-0005` → `wcf-0006` (OS3).
- AC4: `tests/test_task.py`, `["wcf-0005", "spike", "WCF-0099"]` → `wcf-0006`; and `tests/test_project_tasks.py`,
  branches `task/spike` and `task/WCF-0099` beside `wcf-0005` give `wcf-0006`.
- AC5, AC6: `tests/test_task.py`, `next_task_id([])` and `next_task_id(["abc-0001", "wcf-0002"])` raise
  `NoNextTaskIdError` with the exact text. `tests/test_task_command.py`, parametrized: the CLI on a repository with
  no `agent-notes` and no task branch, and on one with branch-only `abc-0001` and closed `wcf-0002`, exits 1 with
  the exact stderr, and `git for-each-ref` is unchanged.
- AC7: `tests/test_task_command.py`. A `git` stand-in on PATH (`scripted_stand_in`) runs the real git, but before
  its first `push` runs a competing `python -m foundry.cli task create store` in the same foundry, with real git
  on PATH. The test's `cli.main(["task", "create", "store"])` exits 1 with a line starting `error: ` on stderr.
  The repository has one new task branch and one new `agent-notes` commit, both the competitor's, and no second
  task notes dir.
- AC8: the existing create tests pass unchanged; the seeded repository already mixes the prefixes `tst` and `cls`,
  and `test_the_first_task_creates_agent_notes_as_an_orphan_holding_only_its_files` has no task at all.
- AC9: `tests/test_docs.py` passes unchanged.
- AC10: `tests/test_task_command.py`, `parse_args(["task", "create", "store"])` gives `task_id is None`, and
  `task create --help` (its SystemExit and captured stdout) shows `PROJECT [TASK]` and the default's help text.
- AC11: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov`, and mypy, vulture, pylint.

## Docs
- `README.md`: the command table's row becomes `foundry task create PROJECT [TASK]`, adding "Without TASK, the next
  task id: the prefix the project's tasks use, and one more than the highest number taken." The task id line says
  "a prefix of lowercase ASCII letters, `-`, then a number of four or more digits".
- `GLOSSARY.md`: **Task id** as TASK.md's "Terms" sharpens it.
- `ARCHITECTURE.md`: `project_tasks.py`'s codemap row says "creating them, under an id given or the next one".
- Docstrings: `project_tasks.py`'s module and `create_task`'s; `task.py`'s `_TASK_ID` comment; the `create`
  parser's TASK help, "task id, e.g. wcf-0042 (default: the next one after the highest the project has taken,
  with its prefix)".
