# Review: wcf-0027

## Round 1 (reviewing 2585b62)

TASK.md reviewed: the version written by `1aeba97` ("task drafted and approved"), signed `G` by the architect identity. That identity is shared with the planner, so I cannot tell the two apart. The earlier commit `a137f7d` ("Add task wcf-0027") is the human's, signed. No other commit changed TASK.md.

### TASK.md changed by another role
None.

### Earlier findings
None (first round).

### Standards
No hard violations. Rules 1, 3 and 6 of ARCHITECTURE.md hold. ADR 0012 supersedes only the layout in ADR 0006 and leaves 0006 unedited. GLOSSARY.md is followed.

- **R1 (Follow-up)** `src/foundry/commands/run.py:45-49`: `turn` is `None` when a role was given, and `assert role_name is not None` is there only for mypy. Nest the `role_for_turn` call in the `with` block's `if role_name is None:` branch and drop the assert.
- **R2 (Follow-up)** `src/foundry/commands/task.py`, `close_main` and `reopen_main`: near-duplicate composition roots (mild Duplicated Code). They follow `create_main`, as the task asks. Accept as is.

### Spec
Every acceptance criterion has code and a test; none is missing, and there is no scope creep.

- **R3 (Follow-up)** `tests/test_run.py:129`: the closed-task refusal is tested through `require_open`, not through `main`. The code is correct (`require_open` at `run.py:44` runs before `prepare_launch` at `run.py:50`, on both the with-ROLE and no-ROLE paths), but a reordering would go unnoticed. Accept as is, or add a `main` test.
- **R4 (Follow-up)** `src/foundry/project_tasks.py:61-63`: `is_closed` tests for the closed `TASK.md`, while `close` and `reopen` test the dir. Only a hand-edited branch can make them disagree. Accept as is.
- **Noted, accepted:** `tests/test_task.py` was not split as DESIGN.md says. The Task and `ProjectTasks` tests share the repository fixtures, so one file is fine.

### Behaviour
No findings. Every refusal is raised before `move_dir`, `commit` and `push_atomic`. A dir present under both `open/` and `closed/` is refused by `close`, `reopen` and `run`, and nothing is pushed. A signing failure happens before the push, and the push is never forced. Bad ids are a `FoundryError` before any git call. An old-layout task is reported as "doesn't exist", as the task says.

### Not checked by me
- The PR #34 description (the migration snippet): `gh` returns HTTP 401 in this sandbox. The dev's PROGRESS.md says it is there.
- pytest, ruff and mypy: none is installed in this sandbox, and `uv run pytest` failed to spawn for the Behaviour reviewer. I rely on the dev's report and on CI being green. The dev should confirm both the PR body and the checks in the answer.

Summary: Standards 2 findings, Spec 3, Behaviour 0. None blocks.

Verdict: approved
