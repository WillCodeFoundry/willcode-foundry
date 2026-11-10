# Learnings
- 2026-11-09 [testing] — The guard-bash hook refuses any shell command whose text sets git's hooks path, even on a
  throwaway repo in the scratchpad, and even inside a heredoc writing notes. So the AC7 race test uses a `git`
  stand-in on PATH (`scripted_stand_in`), not a git hook, to run the competing create just before the push.
- 2026-11-09 [testing] — `project_repository`'s seeded tasks, `tst-0000` and `cls-0000`, already use two prefixes,
  so a test of create without TASK must remove them first, or it gets the mixed-prefix refusal.
- 2026-11-09 [testing] — Two creates of the same task id, with the same identity, template and stand-in signer,
  in the same second, make bit-identical commits; the second atomic push is then a no-op and exits 0. A race test
  must make the competitor's commit differ, e.g. with `GIT_COMMITTER_DATE`. In real use it would only happen for
  one person creating the same task twice within a second, with the same result either way.
- 2026-11-09 [proposal] — code-review skill: it always spawns five sub-agents, even for a round whose fix diff is a
  three-line test-only rename. Round 6 of wcf-0033 ran the axes inline instead. Proposal: let a later round run the
  axes inline when the fix diff is a few lines, and say so in the round.
- 2026-11-10 [proposal] — reviewer ROLE.md, `no-agreement`: it holds whenever a Blocking finding is open after the
  third code round, even when the finding is new and the dev has not disagreed. In wcf-0033 round 7, the human
  reopened the code (D2, D3) after an approval. That made a fourth round, and its first Blocking findings went to the
  human instead of the dev. Proposal: count rounds from the latest human-approved change, or apply the rule only to a
  finding the dev has answered and the reviewer still holds open.
