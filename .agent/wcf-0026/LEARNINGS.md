# Learnings
- 2026-10-29 [decision] — Dirty-conflict detection uses `git read-tree -m -u -n <local> <origin>` (dry run): gives git's own reason without touching the tree, so both checkouts can be vetted before either moves. Rejected `merge --ff-only` on code first: a later notes refusal would leave code moved.
- 2026-10-29 [testing] — A refusal still runs `fetch`, so origin-tracking refs move; tests snapshot HEAD, status, stash and `refs/heads` only.
