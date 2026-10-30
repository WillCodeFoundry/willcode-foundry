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

## Round 3 (reviewing d8b387d)

TASK.md is unchanged: the last allowed version is still `c283670`, signed by the shared architect/planner identity (the known limit in ROLE.md applies). No other commit touched it.

This round reviews the fix diff `75b822f...d8b387d` (b3a530d, d8b387d). Check results at d8b387d, with `SSH_AUTH_SOCK` unset: `uv run --group dev pytest` passes in full, `ruff check .` passes, `ruff format --check .` passes, and `mypy` passes.

Note for the human: this reviewer sandbox started with both checkouts behind origin (notes 1 commit behind, code 2 commits behind). That is the wcf-0025 symptom this task fixes, because the sandbox was launched by the runtime from before this change. I fast-forwarded both by hand before reviewing.

### Open findings from earlier rounds
- **R1** (comment overclaimed): closed by d8b387d. `src/agent_runtime/session_setup.py:72-73` now names the task-branch switch as the one exception, which matches the code.
- **R2**: accepted as is (unchanged).
- **R3**: deferred, Follow-up. TASK.md puts it out of scope, and the R1 comment now documents it.
- **R4**: accepted as is (unchanged).
- **R5**: deferred, Follow-up. The non-checkout notes dir is still reported as "detached". The dev noted it for later.
- **R6** (Blocking, signing in `push_to_origin`): closed by b3a530d. `tests/agent_runtime/test_session_setup.py:227` commits with `-c commit.gpgsign=false`. All 25 tests in the file pass, both with and without an SSH agent, and the six tests R6 named now reach their assertions. The Behaviour agent reproduced the failure with b3a530d reverted. Every other commit in the file either already turns signing off (lines 301, 336, 375) or runs before `session_setup` adds the role gitconfig (line 56).

### Standards
No new findings. The fix is a one-line test change that follows the idiom the file already uses, plus a comment.

### Spec
No new findings and no scope creep. Every acceptance criterion R6 had left untested is now covered by a passing test, and the criterion "`uv run pytest`, `ruff check`, `ruff format --check` and `mypy` pass" is met.

### Behaviour
No new findings. d8b387d changes only a comment, so it had nothing to run. b3a530d is verified as above.

### Summary
Standards 0, Spec 0, Behaviour 0 new findings; 0 Blocking. Open follow-ups: R3 and R5 (deferred).

Verdict: approved

## Round 4 (reviewing d0f1788)

The human asked for this round after the dev's post-approval CI fix. TASK.md is unchanged. The last allowed version is still `c283670`, signed by the shared architect/planner identity (the known limit in ROLE.md applies), and no other commit touched it.

This round reviews the fix diff `d8b387d...d0f1788`. That is one commit, test-only: the `commit_locally` helper in `tests/agent_runtime/test_session_setup.py`.

Checks at d0f1788 were run CI-style, with every `AGENT_*` variable and `SSH_AUTH_SOCK` unset. The full `uv run --group dev pytest` suite passes, and so do `ruff check .`, `ruff format --check .` and `mypy`.

Note for the human: this sandbox started with the code checkout 1 commit behind origin (missing d0f1788). That is the same wcf-0025 symptom as in round 3, and it persists until PR #28 merges. I fast-forwarded it by hand before reviewing.

### Open findings from earlier rounds
- **R1**: closed (unchanged).
- **R2**: accepted as is (unchanged).
- **R3**: deferred, Follow-up (unchanged).
- **R4**: accepted as is (unchanged).
- **R5**: deferred, Follow-up (unchanged).
- **R6**: closed (unchanged).

### Standards
- **R7 (Follow-up, judgement call): Duplicated Code at `tests/agent_runtime/test_session_setup.py:231`.**
  - What: `commit_locally` is the third module-local copy of "commit with the kit's hooks off". The other two are `commit_unchecked` (`tests/agent_runtime/test_git_hooks.py:78`) and `commit` (`tests/agent_runtime/test_claude_hooks.py:131`).
  - Standard: CONTRIBUTING.md:31 says "Shared helpers live in `tests/support/`".
  - Naming: the new name stresses that the commit is unpushed, while `commit_unchecked` stresses that the hooks are skipped. The name reads correctly at its call sites, so it doesn't mislead.
  - Who hits it: a developer who later changes how tests get past the hooks would edit three files. That is rare.
  - Direction: accept as is for this task. Moving one shared helper into `tests/support/` is an optional follow-up.
  - Deferred: accepted as is for this task; moving one shared hook-skipping commit helper into `tests/support/` is noted as a follow-up.
- Otherwise: the three call-site hunks (lines 318, 353, 392) breach no standard, and the docstring follows AGENTS.md's writing rules.

### Spec
No new findings and no scope creep. The three edited tests still check their criteria:
- **Ahead left as is:** lines 317-323 still make a real unpushed commit in each checkout and assert both tips are unchanged.
- **Diverged refusal lists local subjects:** with hooks off, nothing rewrites the message, so line 362 still checks the exact subject committed at line 353.
- **No change after a refusal:** `snapshot()` is still taken after the local commit, and it compares the same state.

The criterion "`uv run pytest` … pass" now holds CI-style, not only in an agent sandbox.

### Behaviour
No new findings.
- **The fix is what makes CI pass:** in a throwaway clone with d8b387d's version of the test file, `test_unpushed_commits_are_left_as_they_are`, `test_a_diverged_branch_is_refused_naming_the_local_commits` and `test_a_refusal_in_the_notes_leaves_the_code_checkout_where_it_was` fail CI-style. At d0f1788, all 25 tests in the file pass both CI-style and with the sandbox environment.
- **No other test git call runs the kit's hooks:** `push_to_origin` commits in a separate clone that doesn't share the checkout's hook config, and turns signing off. The fixture's seed commit runs before `session_setup`. The other git calls on set-up checkouts run none of the kit's three hooks (`pre-commit`, `pre-push`, `prepare-commit-msg`).
- **The `-c` override doesn't leak:** it applies to one git process only and is never written to config. No snapshot compares config.

### Summary
Standards 1 new finding (R7, Follow-up), Spec 0, Behaviour 0; 0 Blocking. Worst per axis: Standards, the hook-skipping commit helper duplicated across three test modules (R7). Open follow-ups: R3, R5 (deferred) and R7.

Verdict: approved
