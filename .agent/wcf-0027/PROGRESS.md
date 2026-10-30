# Progress

## Done
- Read TASK.md, AGENTS.md, ARCHITECTURE.md, ADR 0006 and the code in `src/foundry/{task,project_clone}.py`,
  `src/foundry/commands/{task,run}.py`. TASK.md has no open questions and is consistent with the code.

## In progress
- Design plan below, written before any code. No code changed.

## Next
Proposed design (for the dev, or for me if the human says to implement):
1. `task.py` (design rule 1: the only place the paths are spelled): add `OPEN_DIR`/`CLOSED_DIR` under `NOTES_ROOT`
   (`.agent/tasks/open`, `.agent/tasks/closed`). `Task.task_notes_dir` and `task_file`/`turn_file` become the open
   paths, so `session.py` and `run.py` follow with no change. Add `Task.closed_notes_dir`.
2. `project_clone.py`: add `move(src, dst)` (rename in the checked-out files; `commit` already does `add --all`, so
   git records a rename and every file stays byte-identical). No other new git surface.
3. `task.py`: `close(clone, task)` / `reopen(clone, task)` sharing one private `_move`. Check out `agent-notes`;
   refuse before any commit or push if the source is missing (already closed / already open vs doesn't exist, three
   distinct messages); commit `Close task <id>` / `Reopen task <id>`; `push_atomic(from_remote={}, from_local=[NOTES_BRANCH])`.
   The unsigned-key message comes from `ProjectClone.commit` already, so it matches `create`.
4. `create`: the existing-dir check must cover both `open/<id>` and `closed/<id>` and name the one found.
5. Closed-task refusal for `run`: `task.is_closed(clone, task)` reads `closed/<id>/TASK.md` on the remote via
   `ProjectClone.read`. `commands/run.py:main` currently makes a clone only when ROLE is absent; make it open one clone
   always and check closed first, before `prepare_launch`, reusing that clone for `read_turn`.
6. `commands/task.py`: `close`/`reopen` subparsers and mains, same composition-root shape as `create_main`
   (no template, no confirmation).
7. Tests (TDD, seams in TASK.md): `tests/test_task.py` (real bare repo: paths, byte-identical move, one signed commit,
   refusals push nothing, no-key message), `test_run.py`, `test_session.py`, `test_task_contract.py`, cli parsing,
   `test_docs.py`.
8. Docs: README command table + `agent-notes` row; GLOSSARY ("Task notes dir", new "Open task"/"Closed task");
   new `docs/adr/0012-...md` superseding 0006 (options: `.agent-archive/`, migrate command) + row in `docs/adr/README.md`;
   PR description with the one-off bash move snippet.

Risks noticed:
- Git tracks no empty dirs, so a "task dir" is only its files; `exists` on a dir is fine because creation always writes TASK.md.
- Sandboxes created before this change keep the old `AGENT_TASK_NOTES_DIR`; explicitly out of scope.
- This task's own notes still sit at `.agent/wcf-0027/` and are part of the owner's manual move after merge.

## Blockers
- `roles/architect/ROLE.md` says only "You are the architect": it gives no method, definition of done or next role.
  Question for the human: should I (a) implement this task myself on `task/wcf-0027`, or (b) stop at this design and
  hand the turn to `dev`? I assumed neither and wrote `human` in `TURN`.
