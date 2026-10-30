# Learnings
- 2026-10-30 [decision] — Kept Task and ProjectTasks tests in one `tests/test_task.py`: they share the bare-repo and signer fixtures, and a second file would import from the first or duplicate them.
- 2026-10-30 [decision] — `Task.__post_init__` requires an already-lowercase id; `from_id` lowercases. So the "not valid" message for `X.LOCK` quotes `x.lock`.
