# Progress

## Done
- All acceptance criteria implemented and tested in `tests/agent_runtime/test_session_setup.py`; `session_setup.py` fast-forwards both checkouts (commit on task branch: "fix(runtime): bring both checkouts to origin's tip on every launch").
- Refusals (diverged, dirty-conflict via `git read-tree -m -u -n` dry run, notes worktree detached/wrong branch) are all checked before either checkout moves.
- `uv run pytest`, `ruff check`, `ruff format --check`, `mypy` pass.

Status: ready for review

## In progress

## Next
- Reviewer: review the task branch. The sbx tier is run by the human by hand.

## Blockers
