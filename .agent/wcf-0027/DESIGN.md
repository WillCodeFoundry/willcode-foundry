# Design: wcf-0027

## Decisions
- A task's notes dir depends on a `Status` (`OPEN` or `CLOSED`), carried by `Task` as an immutable field:
  `Task(id, status)`, a frozen dataclass. Its properties derive every name and path from the id and the status.
  This rules out a status that changes on a task, and a default status.
- `Task.__post_init__` validates the id only: ASCII, lowercase, and a valid ref component. The messages are today's.
  A bad id is a `FoundryError`. The status is not checked at run time: mypy checks `status: Status`. Answers R13.
  Replaces "a non-`Status` is a `TypeError`".
- `Task.from_id_and_status(id, status)` lowercases an ASCII id, then constructs. `Task.as_open(id)` and
  `Task.as_closed(id)` are one-line wrappers for it. A non-ASCII id is not lowercased, so `__post_init__` rejects
  it, as today.
- `Status` is a plain enum: its values are not paths, and no message is built from a member's name or value.
  `task.py` maps each status to its dir. Answers R11.
- A `Task` whose status matters comes from the repository, never from the caller's guess. `ProjectTasks` finds a
  task in one place, `get_task_by_id`: it checks out `agent-notes` and builds the `Task` with the status of the dir
  that exists. It raises `TaskNotFoundError` when neither exists, and a plain `FoundryError` naming both when both
  do. Answers R1. Replaces "No lookup object, snapshot or precondition helper exists … rules out a `find`
  function", "A task's status is the caller's expectation, not a fact", and `is_closed` reading `TASK.md`.
- `ProjectTasks`' public methods take task ids, and `Task`s come out of them, never go in: `get_task_by_id`,
  `create_task`, `close_task`, `reopen_task`, `read_task_turn`. The command roots never build a `Task`. `as_open` is
  used only where open is a fact: in `create_task` for the new task, and in `session.from_env` (a sandbox is made
  only for an open task). The status asserts in `ProjectTasks` and `session.py` go. Answers R1. Replaces
  `create`, `close`, `reopen`, `is_closed` and `read_turn` taking a `Task`, and their asserts.
- `TaskNotFoundError(FoundryError)` is new, in `project_tasks.py`. Its message says the task doesn't exist and
  names both dirs. `create_task` catches it, and only it, to know the id is free; any other error propagates.
  No other code catches it.
- `create_task` calls `get_task_by_id` first. When a task is found, it refuses naming that task's notes dir. Only
  then does it refuse on an existing `task/<id>` branch, so a closed task that kept its branch gets the message
  naming its dir. Answers R3.
- `close_task` and `reopen_task` call `get_task_by_id`: a missing task is refused by its "doesn't exist" message,
  a task already in the target state by "already closed" or "already open". Then they move the dir.
- `foundry run` refuses every task that doesn't exist, as well as a closed one, before any sandbox. This goes
  beyond TASK.md, by the human's choice: it is simpler than an exception for one case, and today's behaviour
  starts a sandbox on a missing notes dir. Replaces "A task in neither dir is handled as today".
- One function in `commands/run.py` picks the role to launch, given the `ProjectTasks`, the project name, the task
  id, ROLE or None, and the known roles. It gets the task, refuses a closed one with the
  `foundry task reopen PROJECT TASK` command, then reads the turn only when ROLE is None. It returns the role and
  the `Task`. `main` calls it inside the scratch clone, then `prepare_launch`, so "was a ROLE given?" is decided
  once. Without ROLE, the task is looked up twice: one more fetch per launch, accepted for the id-in rule above.
  Answers R7 and R8. Whether `require_open` survives as a helper is the dev's choice.
- A scratch `ProjectTasks` is built one way: `ProjectTasks.in_scratch_clone(url, env)`, a context manager yielding
  a `ProjectTasks` on a temporary clone. All four composition roots use it. `close_main` and `reopen_main` stay
  separate subcommands; the dev decides whether they share a body. Answers R6.

## Modules and seams
- `src/foundry/task.py`: `Status`, a plain enum; `Task(id, status)` with `from_id_and_status`, `as_open` and
  `as_closed`; `branch`, `task_notes_dir`, `task_file` and `turn_file` derive from the id and the status, with
  `OPEN_DIR` and `CLOSED_DIR` beside `NOTES_ROOT`. No `isinstance` check. It holds names, validation and
  `load_template`, does not import `ProjectClone`, and stays the one place a task's names are spelled.
- `src/foundry/project_tasks.py` (new): `ProjectTasks(clone)`, holding no state of its own, with
  `in_scratch_clone(url, env)`, `get_task_by_id`, `create_task`, `close_task`, `reopen_task` and `read_task_turn`,
  all taking a task id; and `TaskNotFoundError`. `close_task` and `reopen_task` move the dir with
  `ProjectClone.move_dir`, commit as `Close task <id>` or `Reopen task <id>`, and push with
  `push_atomic(from_remote={}, from_local=[NOTES_BRANCH])`. Each operation returns the resulting `Task`, so the
  commands print its lowercased id. Seam: tested against a real bare repository and the stand-in signer, as in
  `tests/test_task.py`.
- `src/foundry/project_clone.py`: adds `move_dir(src, dst)`: moves one directory with everything in it, creates
  the destination's parents, and fails if the destination exists. Seam: the only door to git (design rule 3).
- `src/foundry/commands/task.py`: `close` and `reopen` subparsers with `close_main` and `reopen_main`, the same
  composition-root shape as `create_main`, with no template and no confirmation. All three pass the task id to
  `ProjectTasks` and build no `Task`. The `create` help text names the new dir.
- `src/foundry/commands/run.py`: the role-picking function above, and `main` calling it inside
  `in_scratch_clone`, then `prepare_launch` with the returned `Task`. Seams: that function, tested against a real
  repository with and without ROLE (criterion 10), plus `prepare_launch` and `role_for_turn` as in
  `tests/test_run.py`.
- `src/foundry/session.py`: `from_env` builds its task with `Task.as_open`. No status assert.
- Tests: `Task` properties and factories, and `ProjectTasks` against a real repository, including
  `TaskNotFoundError`, the both-dirs error and `create_task` on a closed id that kept its branch. `test_run.py`,
  `test_session.py`, `test_task_contract.py` and the `cli` parsing tests use the new names and paths;
  `tests/test_docs.py` checks the README's command table.
- Docs: README (command table and the `agent-notes` row), `GLOSSARY.md` (one sentence in "Open task, Closed task":
  a task's status is open or closed, named `Status` in the code; no new heading), the codemap rows for `task.py`
  and `project_tasks.py` in `ARCHITECTURE.md`, and the new ADR below.

## Design rules and ADRs
- ARCHITECTURE.md rule 1 (one spelling per shared name): the open and closed paths are spelled only in
  `foundry/task.py`, and `test_task_contract.py` holds the rest to it.
- Rule 3 (one door to each outside system): all git goes through `ProjectClone`, which gains `move_dir` and
  nothing else; `ProjectTasks` is built on it.
- Rule 6 (fail fast): no retry on a concurrent push to `agent-notes`; a non-forced push that loses the race fails
  with git's error. No run-time type check on `Task.status` (R13). Both dirs existing is refused, not resolved.
  `TaskNotFoundError` is the one exception caught, by `create_task`, because the design expects it there.
- ADR 0006 (accepted, not edited) is superseded by a new ADR 0012, "Task notes are split into open and closed",
  for the dev to write: task notes sit under `.agent/tasks/open/<id>/` or `.agent/tasks/closed/<id>/`; options
  rejected are a separate `.agent-archive/` root (hooks would need a second root) and a migrate command (the
  migration is a one-off). Add it to the "Projects and tasks" row in `docs/adr/README.md`.
- ADR 0011 (a task's turn is one line): unchanged.

## Leave alone
- `src/agent_runtime/` and the git and Claude hooks; `NOTES_ROOT` stays `.agent`.
- `task/<id>` branches, sandboxes and `sessions/` dirs: close and reopen never touch them.
- Existing tasks on any `agent-notes` and sandboxes created before this change: the owner moves and deletes them.
- The turn's meaning: the `TURN` file's format, `HUMAN`, and `role_for_turn`. Reading the turn only moves.
- `prepare_launch` and `session.open_or_create` keep taking a `Task`.
