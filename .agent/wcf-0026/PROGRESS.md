# Progress

## Done
- All acceptance criteria implemented and tested in `tests/agent_runtime/test_session_setup.py`; `session_setup.py` fast-forwards both checkouts (`75b822f`).
- Refusals (diverged, dirty-conflict via `git read-tree -m -u -n` dry run, notes worktree detached/wrong branch) are all checked before either checkout moves, except the existing task-branch switch (out of scope).
- Review round 2: R6 fixed in `b3a530d` (`push_to_origin` commits unsigned); R1 fixed in `d8b387d` (comment names the switch exception). R3 and R5 deferred; answers in `REVIEW.md`.
- `uv run pytest` (also with no SSH agent: `env -u SSH_AUTH_SOCK`), `ruff check`, `ruff format --check`, `mypy` pass at `d8b387d`.

Status: ready for review

## In progress

## Next
- Reviewer: round 3 on `d8b387d`. The sbx tier is run by the human by hand.
- Suggested follow-ups (not this task):
  - R3: `_switch_to_task_branch` moves the code checkout before later refusals when it started on another branch.
  - R5: a notes directory that isn't a git checkout is reported as "detached"; tell the two apart.

## Blockers
