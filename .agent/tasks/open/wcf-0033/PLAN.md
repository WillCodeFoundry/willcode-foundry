# Plan: wcf-0033

## Approach
`task.py` gains a pure function, `next_task_id(taken_ids)`, that parses each id with the task id pattern, refuses
a name that isn't a task id, and returns the next id or raises `NoNextTaskIdError`. Because: DR1, a task's names are
spelled only in `task.py`. A read-only `ProjectTasks.taken_task_ids()` returns only the task ids taken by task
branches and by the dirs under `OPEN_DIR` and `CLOSED_DIR` (one fetch of `agent-notes`). Amended: R20. Because: D3
made `next_task_id` refuse such a name and `taken_task_ids` keep only task ids, as Steps 2 and 3 say. In the `foundry task create` command,
TASK becomes optional. A function `task_id_to_create(project_tasks, task_id)` there returns the given id when it
is not None, even `''`, and otherwise `pick_next_task_id(project_tasks)`, which returns
`next_task_id(project_tasks.taken_task_ids())`, adding "Give TASK…" to the refusal. `create_main` calls
`ProjectTasks.create_task` with `task_id_to_create`'s id, with no branch of its own, so a given TASK, `''` included,
takes the same path as before (AC8). Because: DR7. Amended: D3. Because: the human's review of 83a4dfc: `args.task_id or …` picked an id for `''`. It is not
python-smells 5.2's hidden query: `create_task` still takes a `str`, and `pick_next_task_id` is callable alone. `create_task` is unchanged by this task. A race
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
   among that task prefix's ids only, formatted `{task_prefix}-{number:04d}`. `taken_ids` are task ids: one that
   isn't is refused with `Task`'s invalid-id error, from `_parse_task_id(task_id) -> re.Match[str]`, which
   `Task.__post_init__` also calls. Amended: R26. Because: it parses as well as refuses, and every `require_` in
   `src/` only checks. A public `is_task_id(name) -> bool` keeps the parsing in `task.py`. Because:
   DR1. Amended: D3. Because: the human's review of 83a4dfc: `taken_task_ids` returns only task ids.
   Its locals are `task_prefix` and
   `task_prefixes`, never `prefix`. Unit tests first. Amended: R7. Because: entry 7.
3. `project_tasks.py`: `ProjectTasks.taken_task_ids() -> frozenset[str]`: the dir names under `OPEN_DIR` and
   `CLOSED_DIR` (none without `agent-notes`), plus each branch starting with `BRANCH_PREFIX`, with `BRANCH_PREFIX`
   cut off, keeping only those `is_task_id` accepts. Amended: D3. Because: the human's review of 83a4dfc: the method returns what its name says. It
   changes no file. `create_task` keeps its body as on the default branch. Amended: R7. Because: "prefix
   removed" read as the task id's prefix. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
4. `commands/task.py`: the shared `task_arguments` parent splits into a PROJECT parent and a TASK parent, so
   `create` takes TASK with `nargs="?"`. A module function `pick_next_task_id(project_tasks)` returns
   `next_task_id(project_tasks.taken_task_ids())` and re-raises `NoNextTaskIdError` with the hint;
   `task_id_to_create(project_tasks, task_id)` returns `task_id` if it is not None, else `pick_next_task_id`'s;
   `create_main` calls `project_tasks.create_task(task_id_to_create(project_tasks, args.task_id), template)`. Amended: D3. Because: the human's review of 83a4dfc: DR7, and `''`. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
5. Docs, below.

## Names
- `next_task_id`, `NoNextTaskIdError`: "task id" from GLOSSARY.md; "next" from TASK.md's goal.
- `task_id_to_create`: the id `create_task` is given, named for that role. `is_task_id`, `_parse_task_id`:
  GLOSSARY.md's **Task id**; `_parse_task_id` is named for what it returns, the parse, refusing a name that isn't a
  task id. Amended: D3. Because: the human's review of 83a4dfc. Amended: R26. Because: `require` in `src/` names a
  check that returns None.
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
  or, when the winner pushed before the loser's `create_task` read, its "task … already exists" refusal.
- `create PROJECT ""` (AC8): `Task`'s `error: task id '' is not valid: use lowercase letters, '-', then four or more
  digits (e.g. wcf-0042)`, as on the default branch. Amended: D3. Because: the human's review of 83a4dfc. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.

## Tests
- AC1: `tests/test_project_tasks.py`, `ProjectTasks.taken_task_ids` on `project_repository`, its seeded tasks
  removed and `wcf-0030` open, `wcf-0032` closed written with `edit_notes`, and `task/wcf-0033` made with
  `project_repository.git("branch", …)`, returns exactly those three ids and changes no ref. `tests/test_task_command.py`:
  the same repository through `cli.main(["task", "create", "store"])` with `enter_foundry` and `write_foundry`,
  asserting the two printed lines, exit 0, `head("task/wcf-0034") == head("main")`, the template under
  `.agent/tasks/open/wcf-0034/`, and the `agent-notes` commit subject `Add task wcf-0034`; the rest of "the same as
  `create PROJECT wcf-0034`" is `create_task`'s own tests, since it is the same call. Amended: R5. Because: AC1 says
  "the same as … would leave". Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
- AC2: AC1's `taken_task_ids` test in `tests/test_project_tasks.py`, which takes one id of each kind, shows that
  open, closed and branch-only ids are all taken; that `next_task_id` follows the highest number is AC3's test.
  Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path. Amended: R23. Because: `next_task_id`'s rules are proved in `tests/test_task.py`. Amended: R28. Because: the parametrized test repeated
  AC1's, so it is dropped.
- AC3: `tests/test_task.py`, `next_task_id` parametrized: `wcf-0041` → `wcf-0042`, `wcf-9999` → `wcf-10000`,
  `wcf-00041` → `wcf-0042`; also `wcf-0001`, `wcf-0005` → `wcf-0006` (OS3).
- AC4: `tests/test_project_tasks.py`, branches `task/spike` and `task/WCF-0099` and a notes dir `spike` beside
  `wcf-0005`: `taken_task_ids()` is `{"wcf-0005"}`. `tests/test_task.py`: `next_task_id(["wcf-0005", "spike"])`
  raises `Task`'s invalid-id error. Amended: D3. Because: the human's review of 83a4dfc: the filtering moved into `taken_task_ids`. Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.
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
  No `tests/test_project_tasks.py` test of it: `taken_task_ids` only reads ids, which AC1's and AC2's tests show.
  Amended: R23. Because: through `taken_task_ids` it re-proved `next_task_id`.
- Each id counted once (AC6): `taken_task_ids` returns a set, so a branch and its notes are one id; `tests/test_task.py`
  shows `next_task_id` counts a repeated id once. No `tests/test_project_tasks.py` test of it. Amended: D2. Because:
  the human wants the entry point to pick the id and then take create_task's own path. Amended: R23. Because: a
  frozenset can't hold an id twice, so that test could not fail for the reason it named.
- AC7: `tests/test_task_command.py`. A `git` stand-in on PATH (`scripted_stand_in`) runs the real git, but before
  its first `push` runs a competing `python -m foundry.cli task create store` in the same foundry, with real git
  on PATH. The test's `cli.main(["task", "create", "store"])` exits 1 with a line starting `error: ` on stderr.
  The repository has one new task branch and one new `agent-notes` commit, and no second task notes dir. The
  stand-in writes the tips of `agent-notes` and of the new task branch to a file once the competitor finishes, and
  the test asserts both final tips equal them. Amended: R4. Because: the count alone can't tell whose commit
  survived. Setup: the seeded tasks' dirs removed with `edit_notes(remove=…)` and `wcf-0030` open written with
  `edit_notes`, so both creates pick `wcf-0031`. Amended: R10. Because: the seeded `tst-0000` and `cls-0000` tie,
  and both creates would refuse before any push.
- AC8: `tests/test_task_command.py`, `cli.main(["task", "create", "store", ""])` exits 1 with the invalid-id
  error, and `git for-each-ref` is unchanged. Amended: D3. Because: the human's review of 83a4dfc. The existing create tests pass unchanged; the seeded repository already mixes the prefixes `tst` and `cls`,
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
- `ARCHITECTURE.md`: `project_tasks.py`'s codemap row adds "reading the task ids their notes and task branches take"
  (Amended: D2. Because: `ProjectTasks` no longer creates under the next id);
  `task.py`'s row (`ARCHITECTURE.md:29`) adds "and `next_task_id`, which picks the next task id from the taken
  ones". Amended: R2. Because: the codemap is where a reader looks for it.
- Docstrings: `project_tasks.py`'s module adds, after "so it writes on what it read": "A write may follow a
  separate, earlier read, such as taken_task_ids before create_task. The write fetches again. Its own checks refuse
  only a change that clashes with its own task, and its atomic push, never forced, refuses any change to NOTES_BRANCH
  since that fetch." Amended: D3. Because: the human's review of
  83a4dfc. Amended: R21. Because: a task created in between under another id is not refused. Amended: R27. Because: the push refuses any change since the write's own fetch, not only a clash. `project_tasks.py`'s module, where "callers pass task ids. Listing is the exception: it reads every
  dir under OPEN_DIR from one fetch" (`:5-6`) adds `taken_task_ids` as a second exception, which takes no id and
  reads the dirs under `OPEN_DIR` and `CLOSED_DIR` from one fetch of `NOTES_BRANCH`, and the task branches from the
  remote's branch list, Amended: R3, R11. Because: the sentence becomes untrue otherwise, and the branches come from
  `git ls-remote --heads`, not the fetch, Amended: D2. Because: the human wants the entry point to pick the id and then take create_task's own path.; `task.py`'s module docstring (`:1`), "what a task's names are, how the next
  task id is picked, and the task template", Amended: R2; `task.py`'s `_TASK_ID` comment; the `create` parser's
  TASK help, "task id, e.g. wcf-0042 (default: the next id with the task prefix most of the project's task ids
  use; ids with other task prefixes are ignored)". Amended: R1, R8, R12. Because: entry 8; bare "prefix" is under
  _Avoid_.
