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

## Round 2 (reviewing 2585b62)

The branch has not moved since round 1. This round settles what round 1 could not check. The code and the three axis reports stand.

### TASK.md changed by another role
None. The last allowed change is still `1aeba97`, signed by the architect identity that the planner shares.

### Earlier findings
- **R1** (Follow-up, `run.py` turn sentinel): still open, deferred.
- **R2** (Follow-up, duplicated `close_main` and `reopen_main`): accepted as is.
- **R3** (Follow-up, no test through `run.main`): still open, deferred.
- **R4** (Follow-up, `is_closed` checks `TASK.md`): accepted as is.

### Checks, run now
Round 1 could not run them, because the dev group was not installed. I ran them in a throwaway clone at 2585b62 after `uv sync --group dev`:
- `uv run pytest` (host tier): all passed.
- `uv run ruff check .` and `ruff format --check .`: clean (146 files already formatted).
- `uv run mypy`: no issues in 98 source files.

This meets the last acceptance criterion.

### PR description
The migration snippet, as pasted by the owner from the PR description, meets the criterion. It moves each `.agent/<id>/` to `.agent/tasks/closed/<id>/`, skips `tasks`, signs the commit (`-S`) and pushes without force. I checked it against the current `agent-notes` layout (`.agent/wcf-0025`, `wcf-0026`, `wcf-0027`). I did not run it.
- **R5 (Follow-up)** The snippet moves every task under `.agent/`, including `wcf-0027` while it is in progress. The owner runs it after merging, and that task is then closed. Accept as is, or let the owner reopen it with the new command.

Summary: no new Blocking findings. One new Follow-up (R5).

Verdict: approved

### Dev answer to round 2
- R1: Deferred: Follow-up, left for a later task.
- R3: Deferred: Follow-up, left for a later task.
- R5: Deferred: the owner reopens tasks still in progress after running the snippet, as the PR body says.

## Round 3 (reviewing 2585b62)

The branch has not moved since round 1. This round checks only the PR #34 description that the dev rewrote for the updated `pr` skill (updated 2026-10-30 15:22 UTC). I read it through the public API, since `gh` gets HTTP 401 here.

### TASK.md changed by another role
None. The last allowed change is still `1aeba97`, signed by the architect identity that the planner shares.

### Earlier findings
- **R1** (Follow-up, `run.py` turn sentinel): deferred.
- **R2**: accepted as is (round 2).
- **R3** (Follow-up, no test through `run.main`): deferred.
- **R4**: accepted as is (round 2).
- **R5** (Follow-up, the snippet closes `wcf-0027` too): deferred. The PR's "For you to do" line now tells the owner to reopen tasks still in progress, so this is covered.

### PR description against the `pr` skill
- Title `[wcf-0027] feat(task): close and reopen tasks`: matches the `git-conventions` form.
- Task: both paths are written out. "All 15 acceptance criteria" matches TASK.md, which has 15. There is one exception line, "For you to do", and no criteria are listed as met. It agrees with the Out of scope items: the owner runs the migration and deletes old sandboxes.
- Summary: two diffs, one for the `agent-notes` layout and one for the files. Both are small and say what matters.
- Evidence: names a test that exists (`tests/test_task.py:359`, and `:398` for the refusals), then gives the round 2 check results and says CI is green. The skill asks for the test as pseudocode, and this names and describes it in prose. That is clear enough, so I accept it.
- Merge Danger: the door is one-way and the reason is right: once the migration runs, the data has to be moved back by hand. The blast radius is one word.
- The extra "Migration" section is not in the template, but TASK.md requires the snippet to be in the description. I accept it. I ran the snippet's `mkdir` and `git mv` loop on a throwaway repo with two old-layout dirs. Both moved under `.agent/tasks/closed/` and `tasks` was skipped. I did not run the commit or the push.

### New findings
- **R6 (Follow-up)** Merge Danger, Blast Radius: "Until the snippet runs, foundry reports every existing task as not existing, so `foundry run` and `close` refuse them." This is only partly true for `foundry run`:
  - Without ROLE, `run` fails in `read_turn` with "has no turn … Name the role to run instead". That message does not say the task doesn't exist.
  - With ROLE, `require_open` passes, because `is_closed` is false, and `run` creates a sandbox whose `AGENT_TASK_NOTES_DIR` (`.agent/tasks/open/<id>`) does not exist on `agent-notes`.

  Suggested wording: "Until the snippet runs, `close` and `reopen` report every existing task as not existing, `foundry run` without ROLE finds no turn, and `foundry run` with ROLE starts a sandbox whose notes dir doesn't exist. Run the snippet before any `foundry run`." The code is as TASK.md asks: refusing unmigrated tasks is out of scope. Only the description is wrong.

Summary: the description follows the `pr` skill. One new Follow-up (R6), and no Blocking findings.

Verdict: approved
