# Design: wcf-0027

## Decisions
- A task's notes dir depends on a `Status` (`OPEN` or `CLOSED`), carried by `Task` as an immutable field:
  `Task(id, status)`. The path under `.agent/tasks/` determines the status. No lookup object, snapshot or
  precondition helper exists. This rules out a status that changes on a task, a default status, and a `find`
  function.
- `Task.__post_init__` validates only superficially: an ASCII, lowercase id that is a valid ref component, and a
  `Status` member. The messages are today's. A bad id is a `FoundryError`, and a non-`Status` is a `TypeError`.
- Callers build tasks with `Task.from_id(id, status)`, which lowercases an ASCII id then constructs, and with two
  one-line wrappers, `Task.as_open(id)` and `Task.as_closed(id)`. A non-ASCII id is not lowercased, so
  `__post_init__` rejects it, as today.
- The operations on a project's tasks move out of `task.py` into a new class, `ProjectTasks`, built with a
  `ProjectClone`: `create`, `close`, `reopen`, `is_closed`, `read_turn`. The class holds no state of its own. This
  rules out module-level functions that each take a clone, and rules out leaving `create` and `read_turn` behind
  as the odd ones out.
- A task's status is the caller's expectation, not a fact: the repository decides. `close` and `reopen` check
  the two paths with `exists` and refuse in the order the criteria list (already closed or already open first,
  then doesn't exist). The status is asserted, as a programming error: `close` takes an open task, `reopen` a
  closed one, `create` an open one. The command roots build them: `close_main` with `as_open`, `reopen_main`
  with `as_closed`. A task is never mutated: the sibling is built with `Task.as_closed(task.id)` or
  `Task.as_open(task.id)`.
- `foundry run` always builds one `ProjectTasks`, calls `is_closed` before `prepare_launch`, and reuses it for
  `read_turn`. The refusal message and the `foundry task reopen PROJECT TASK` command are built in
  `commands/run.py`. This adds one network round trip per launch, and a launch without ROLE no longer needs a
  separate clone. A task in neither dir is handled as today (out of scope).
- Sessions are built for open tasks only. `session.py` asserts `task.status is Status.OPEN` before it writes the
  variables.

## Modules and seams
- `src/foundry/task.py`: adds `Status`; `Task` gains `status` and the three factories; `task_notes_dir`,
  `task_file` and `turn_file` derive from the status, with `OPEN_DIR` and `CLOSED_DIR` beside `NOTES_ROOT`.
  `create` and `read_turn` leave it, and it no longer imports `ProjectClone`: it holds names, validation and
  `load_template`. It stays the one place a task's names are spelled.
- `src/foundry/project_tasks.py` (new): `ProjectTasks(clone)` with `create`, `close`, `reopen`, `is_closed` and
  `read_turn`. `create` refuses on either dir, naming the one found. `close` and `reopen` move the dir with
  `ProjectClone.move_dir`, commit as `Close task <id>` or `Reopen task <id>`, and push with
  `push_atomic(from_remote={}, from_local=[NOTES_BRANCH])`. `is_closed` reads the closed task's `TASK.md` on
  `agent-notes`. Seam: tested against a real bare repository and the stand-in signer, as in `tests/test_task.py`.
- `src/foundry/project_clone.py`: adds `move_dir(src, dst)`: moves one directory with everything in it,
  creates the destination's parents, and fails if the destination exists. It touches only the checked-out files;
  `commit` already stages with `add --all`. Seam: the only door to git (design rule 3).
- `src/foundry/commands/task.py`: `close` and `reopen` subparsers and `close_main` and `reopen_main`, the same
  composition-root shape as `create_main`, with no template and no confirmation. The `create` help text names the
  new dir.
- `src/foundry/commands/run.py`: `main` builds `Task.as_open`, builds one `ProjectTasks`, refuses a closed task
  before `prepare_launch`. Seams: `prepare_launch` and `role_for_turn`, as in `tests/test_run.py`.
- `src/foundry/session.py`: one assertion that the task is open. Nothing else changes.
- Tests: `tests/test_task.py` splits into `Task` properties and factories and `ProjectTasks` against a real
  repository; `test_run.py`, `test_session.py`, `test_task_contract.py` and the `cli` parsing tests move to the
  factories and the new paths; `tests/test_docs.py` checks the README's command table.
- Docs: README (command table and the `agent-notes` row), `GLOSSARY.md`, the codemap rows for `task.py` and
  `project_tasks.py` in `ARCHITECTURE.md`, and the new ADR below.

## Design rules and ADRs
- ARCHITECTURE.md rule 1 (one spelling per shared name): the open and closed paths are spelled only in
  `foundry/task.py`, and `test_task_contract.py` holds the rest to it.
- Rule 3 (one door to each outside system): all git goes through `ProjectClone`, which gains `move_dir` and
  nothing else; `ProjectTasks` is built on it.
- Rule 6 (fail fast): no retry on a concurrent push to `agent-notes`; a non-forced push that loses the race fails
  with git's error.
- ADR 0006 (accepted, not edited) is superseded by a new ADR 0012, "Task notes are split into open and closed",
  for the dev to write: task notes sit under `.agent/tasks/open/<id>/` or `.agent/tasks/closed/<id>/`; options
  rejected are a separate `.agent-archive/` root (hooks would need a second root) and a migrate command (the
  migration is a one-off). Add it to the "Projects and tasks" row in `docs/adr/README.md`.
- ADR 0011 (a task's turn is one line): unchanged.

## Leave alone
- `src/agent_runtime/` and the git and Claude hooks; `NOTES_ROOT` stays `.agent`.
- `task/<id>` branches, sandboxes and `sessions/` dirs: close and reopen never touch them.
- Existing tasks on any `agent-notes` and sandboxes created before this change: the owner moves and deletes them.
- The turn's meaning: the `TURN` file's format, `HUMAN`, and `role_for_turn`. `read_turn` only moves.
