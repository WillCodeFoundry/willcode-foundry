# Task wcf-0026: Bring both checkouts to origin's tip on every launch

## Goal
When foundry relaunches a role's existing sandbox, the role currently works from stale checkouts. `session_setup` fetches `origin` but never moves either local branch forward. A role on its second turn therefore reads `TASK.md`, `PROGRESS.md`, `REVIEW.md` and `TURN` as it left them, and `TASK.md` is imported into its instructions from that stale copy. This happened on wcf-0025: the dev was relaunched, saw no `REVIEW.md` and a `TURN` naming the reviewer, and did nothing. Since ADR 0011, every role's second turn hits this. After this task, every launch, first or relaunch, leaves the code checkout and the notes checkout at origin's tip before the agent starts. A checkout that can't be fast-forwarded makes setup refuse and say what is wrong, and never discards work.

## Acceptance criteria
- [ ] Relaunch, code checkout: if origin's task branch has commits the local branch lacks, then after `session_setup` the local branch is at origin's tip and the files from those commits are present.
- [ ] Relaunch, notes checkout: if `agent-notes` on origin has commits the local branch lacks, then after `session_setup` the notes worktree is at origin's tip. A `REVIEW.md` or `TURN` pushed in between is present and read as origin has it.
- [ ] The notes branch is also brought forward when the notes directory is missing but a local `agent-notes` branch exists.
- [ ] The `TASK.md` imported into the agent's instructions is the one at origin's tip. A test changes `TASK.md` on origin between two runs and checks `~/.claude/CLAUDE.md` still imports the notes checkout's path, whose file now holds the new text.
- [ ] A checkout whose branch is only ahead of origin (unpushed commits, not diverged) is left as it is, and setup succeeds.
- [ ] A checkout with uncommitted changes that don't conflict with the incoming commits is fast-forwarded. The uncommitted changes are still present afterwards, and setup succeeds.
- [ ] Setup raises `SetupError` instead of fast-forwarding when the fast-forward fails. That covers a diverged branch and uncommitted changes that git says the update would overwrite. The error names the checkout (code or notes), its branch and git's reason. In the diverged case it also lists the subject lines of the local commits origin lacks.
- [ ] Setup raises `SetupError` when the existing notes worktree is detached or on a branch other than `$AGENT_NOTES_BRANCH`. The error names what it found and what it expected.
- [ ] Every refusal message, in the same message, gives its diagnosis first. It then points to the README's "Recreating a sandbox", and states that recreating discards the unpushed commits or uncommitted changes it just named.
- [ ] After any refusal both checkouts hold exactly what they held before the run: no commit, reset, stash or file was changed or removed.
- [ ] A first launch behaves as before: both checkouts are on their branches at origin's tip.
- [ ] `uv run pytest`, `ruff check`, `ruff format --check` and `mypy` pass. The tests for these criteria are in `tests/agent_runtime/` and use real git in temporary repositories.

## Out of scope
- Refreshing an agent that is already running. Only the start of a launch matters.
- The wcf-0025 opening prompt.
- Any change to the Stop hook (`session_check`).
- Host-side changes in `src/foundry/`.
- The sbx tier: the human runs it by hand before merging, as CONTRIBUTING.md asks for runtime changes.
- A new ADR or glossary term.
- Changing how `_switch_to_task_branch` behaves when the code checkout is on another branch or `switch` itself fails.

## Context
- `src/agent_runtime/session_setup.py`: `_prepare_checkouts` fetches and then calls `_switch_to_task_branch` and `_add_notes_worktree`. Both reuse existing local branches as they are, and `_add_notes_worktree` returns early when the notes directory exists. `_write_instructions` runs after `_prepare_checkouts` and imports `TASK.md` from the notes checkout.
- `src/agent_runtime/git.py`: `Git` is the one way to run git (`run_captured`, `succeeds`, `current_branch`, `run_visibly`). Use it.
- `src/agent_runtime/claude_hooks.py`: `session_check` and `_unsaved_work` are why the local branches should only ever be behind. A killed or closed session can still leave unsaved work, which is why refusals must never reset or discard.
- `ARCHITECTURE.md` design rule 6 (fail fast, with a message; don't work around it), and the runtime codemap.
- `README.md` "Recreating a sandbox" exists, and `tests/test_docs.py` pins the heading. A message that links to it keeps that heading.
- `tests/agent_runtime/test_session_setup.py` has `test_a_second_run_succeeds_and_changes_nothing` and uses the `session_for`, `created_task`, `origin` and `home` fixtures. `tests/support/` holds `git` and `TASK`. `CONTRIBUTING.md` describes the test tiers.

## Seams to test
- `session_setup.session_setup(session, home)`, in-process against a real local origin. Each case is a push to origin between two runs.
  - Relaunch fast-forwards both checkouts and `TASK.md` is imported fresh. This catches the wcf-0025 bug.
  - Local ahead is untouched. This catches an over-eager reset.
  - Non-conflicting uncommitted changes survive. This catches a refusal on any dirty tree.
  - Diverged, conflicting-dirty and wrong-branch notes worktrees each raise `SetupError`. This catches silent staleness and a destructive fallback, and checks the message content.
  - The state before a refusal equals the state after it. This catches discarded work.
- The existing first-launch and second-run tests stay green. This catches a regression of the first-launch path.

## Terms and decisions
- None. The existing glossary entry "relaunch" covers it, and no ADR is needed.

## Open questions
- None.
