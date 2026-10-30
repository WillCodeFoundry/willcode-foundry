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

## Round 2 (reviewing 75b822f)

Redo of round 1 on the same commit, this time with the checks run: `uv run --group dev pytest`, `ruff check .`, `ruff format --check .`, `mypy`. Round 1 could not run them, so its "approved" rested on reading alone. TASK.md is unchanged (still `c283670`, shared architect/planner identity).

Check results at 75b822f: `ruff check` passes, `ruff format --check` passes, `mypy` passes. **`pytest` fails: 6 tests.**

### Open findings from round 1
- **R1** (comment at `session_setup.py:72` overclaims; shares a cause with R3): still open, Follow-up.
  - Fixed in `d8b387d`.
- **R2** (data clump): accepted as is.
- **R3** (code checkout starting on another branch is switched before a later refusal; out of scope in TASK.md): deferred, Follow-up.
  - Deferred: TASK.md puts changing `_switch_to_task_branch` out of scope; the R1 comment now names the exception.
- **R4** (wrong-branch refusal doesn't say whether work exists): accepted as is.
- **R5** (non-checkout notes dir reported as "detached"): still open, Follow-up.
  - Deferred: rare, and setup still refuses changing nothing; telling "not a checkout" from "detached" needs its own wording and test. Noted as a follow-up.

### New findings
- **R6 (Blocking) — six of the new tests fail on any machine that has no signing key in an agent.**
  - Failing: `test_a_relaunch_brings_both_checkouts_to_origins_tip`, `test_the_notes_branch_is_brought_forward_when_only_its_directory_is_missing`, `test_uncommitted_changes_that_dont_conflict_survive_the_update`, `test_a_diverged_branch_is_refused_naming_the_local_commits`, `test_uncommitted_changes_the_update_would_overwrite_are_refused`, `test_a_refusal_in_the_notes_leaves_the_code_checkout_where_it_was`.
  - Cause: `session_setup` runs `git config --global include.path <role gitconfig>` (`session_setup.py:58`), which turns `commit.gpgsign` on in the tests' throwaway HOME. `push_to_origin` (`tests/agent_runtime/test_session_setup.py:227`) then runs `git commit` in a fresh clone without the repo's `UNSIGNED` override (`tests/support/__init__.py:46`, used by the other tests that commit). With no key in an agent, git exits 128: `error: Couldn't find key in agent? fatal: failed to write commit object`. Each test fails at this commit, before its assertions, so these tests do not currently check relaunch fast-forward, the missing-notes-dir case, dirty-tree survival, the diverged refusal, the conflicting-dirty refusal, or no-change-after-refusal.
  - Who hits it: anyone running `uv run pytest` where the role signing key isn't loaded: CI, the human's machine, and this reviewer sandbox. It reproduces here every run.
  - Evidence the code itself is fine: in a throwaway clone, with only the `push_to_origin` commit made `UNSIGNED`, all 25 tests in the file pass.
  - Violates the criterion "`uv run pytest` ... pass" and leaves the other criteria untested. Direction: make `push_to_origin`'s commit unsigned the way the repo's other tests do; the dev's own run should be unaffected by whether a key is present.
  - Fixed in `b3a530d`: the commit now passes `-c commit.gpgsign=false`, as the file's other test commits do. Verified with `env -u SSH_AUTH_SOCK uv run pytest`: all pass.

### Summary
New findings this round: 1 (Blocking), in tests. Round 1's findings stand as Follow-ups. Worst issue: R6, six failing tests that hide the criteria they exist to check.

Verdict: changes needed
