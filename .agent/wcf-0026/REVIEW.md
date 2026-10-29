# Review wcf-0026

## Round 1 (reviewing 75b822f)

TASK.md: last version written by an allowed commit is `c283670` ("wcf-0026: TASK.md approved"), signed by the architect/planner shared identity (the known limit in ROLE.md applies). The first version, `3f9f89d`, is the human's. No other commit touched it, and the current file equals `c283670`.

Limit of this round: the reviewer sandbox has no pytest (`uv run pytest` fails to spawn), so I did not run the test suite or ruff/mypy. The dev reports them green; CI and the human's run should confirm. Findings come from reading the code and tests, and from the Behaviour agent's reproductions in a throwaway clone.

### Standards
- **R1 (Follow-up)** — `src/agent_runtime/session_setup.py:72`: the comment says every refusal comes before any checkout moves, but `_switch_to_task_branch` (line 70) runs first. If the code checkout is on another branch and a later check refuses, HEAD has already switched. Changing `switch` is out of scope in TASK.md, so the behaviour is acceptable; the comment misleads a maintainer. Same cause as R3. Direction: narrow the comment to say the task-branch switch is the exception.
- **R2 (Follow-up, judgement call)** — Data Clumps: `(label, folder, branch)` travels together into `_refusal` and `_require_fast_forward` (lines 131-137, 140). Three call sites, two checkouts. Direction: accept as is.

### Spec
All acceptance criteria trace to code and a test (relaunch of both checkouts, missing notes dir with a local branch, fresh `TASK.md` import, ahead untouched, non-conflicting dirty survives, diverged and conflicting-dirty refuse, wrong/detached notes refuse, message order, no change after refusal, first launch). No scope creep.
- **R3 (Follow-up)** — "After any refusal both checkouts hold exactly what they held": same cause as R1. Not met only when the code checkout starts on another branch, which TASK.md puts out of scope and the tests don't cover. Direction: accept as is, with the R1 comment fix.
- **R4 (Follow-up)** — `session_setup.py:136`: the wrong-branch refusal says recreating discards "any unpushed commits or uncommitted changes in it" without saying whether there are any. Accurate but not specific. Direction: accept as is.

### Behaviour
- **R5 (Follow-up)** — `session_setup.py:128-135`: if the notes directory exists but isn't a git checkout (a leftover empty directory after a crashed setup), `current_branch()` returns `None` and the message says "it is detached" and talks about unpushed commits that don't exist. Reproduced. Setup still refuses and changes nothing, so only the diagnosis misleads. Rare. Direction: tell "not a checkout" apart from "detached", or accept as is.
- Checked and fine: `read-tree -m -u -n` agrees with `merge --ff-only` for modified, staged and untracked-incoming files, and for unrelated deletes; missing notes dir behind/ahead/diverged; task branch missing on origin.

### Summary
Standards 2 findings, Spec 2 (R3, R4), Behaviour 1; 0 Blocking. Worst per axis: Standards, the overclaiming comment (R1); Spec, same cause as R1 (R3); Behaviour, the misleading "detached" diagnosis (R5).

Verdict: approved
