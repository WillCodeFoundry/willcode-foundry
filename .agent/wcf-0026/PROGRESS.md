# Progress

## Done
- All acceptance criteria implemented and tested in `tests/agent_runtime/test_session_setup.py`; `session_setup.py` fast-forwards both checkouts (`75b822f`).
- Refusals (diverged, dirty-conflict via `git read-tree -m -u -n` dry run, notes worktree detached/wrong branch) are all checked before either checkout moves, except the existing task-branch switch (out of scope).
- Review round 2: R6 fixed in `b3a530d` (`push_to_origin` commits unsigned); R1 fixed in `d8b387d` (comment names the switch exception). R3 and R5 deferred; answers in `REVIEW.md`.
- `uv run pytest` (also with no SSH agent: `env -u SSH_AUTH_SOCK`), `ruff check`, `ruff format --check`, `mypy` pass at `d8b387d`.
- Review round 3: `Verdict: approved`.
- PR opened: https://github.com/WillCodeFoundry/willcode-foundry/pull/28
- CI failed on #28: three tests' local setup commits ran the kit's git hooks, which need the `AGENT_*` variables CI lacks. Fixed in `d0f1788` (those commits skip the hooks, as `test_git_hooks`' `commit_unchecked` does); CI green. Test-only change made after approval.

- Review round 4 (on `d0f1788`): `Verdict: approved`. R7 deferred. PR #28 CI green at `d0f1788`.

Status: approved; PR #28 open, waiting on the human

## In progress

## Next
- The human: run the sbx tier by hand (CONTRIBUTING.md), then merge PR #28.
- Suggested follow-ups (not this task):
  - R3: `_switch_to_task_branch` moves the code checkout before later refusals when it started on another branch.
  - R5: a notes directory that isn't a git checkout is reported as "detached"; tell the two apart.
  - R7: three test modules each have their own hook-skipping commit helper (`commit_locally`, `commit_unchecked`, `commit`); move one into `tests/support/`.

## Blockers
