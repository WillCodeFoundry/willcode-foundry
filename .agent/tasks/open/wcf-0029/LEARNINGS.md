# Learnings
- 2026-11-04 [testing] — With the pattern, two sandboxes for different tasks can no longer have
  colliding slugs: a valid id is already its own slug, and the project part can't absorb a
  `<letters>-` without leaving an invalid task id. `test_session.py`'s collision case now collides
  on the project name (`Foundry` vs `foundry`) instead of on the task.
- 2026-11-04 [testing] — A bulk rename of fixture ids by regex also rewrote the refused-ids list
  (`WCF-0042`, `t1`) into valid ids; the refusal test caught it. Exclude the refused-ids list when
  scripting such a rename.
- 2026-11-04 [tools] — `git push` over SSH once failed with `Permission denied (publickey)` mid-session
  and succeeded on a retry a minute later, with the same key in the agent. Retry once before asking.
