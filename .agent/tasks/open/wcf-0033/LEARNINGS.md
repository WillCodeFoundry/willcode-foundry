# Learnings
- 2026-11-09 [testing] — The guard-bash hook refuses any shell command whose text sets git's hooks path, even on a
  throwaway repo in the scratchpad, and even inside a heredoc writing notes. So the AC7 race test uses a `git`
  stand-in on PATH (`scripted_stand_in`), not a git hook, to run the competing create just before the push.
- 2026-11-09 [testing] — `project_repository`'s seeded tasks, `tst-0000` and `cls-0000`, already use two prefixes,
  so a test of create without TASK must remove them first, or it gets the mixed-prefix refusal.
