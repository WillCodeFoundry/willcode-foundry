# Learnings

- 2026-11-17 [sandbox] — A dry run of an sbx probe, with a stand-in `sbx` whose `env exec` ran its command locally,
  killed this planner's own sandbox: `pkill -x claude` killed Claude Code, and `pkill -x sleep` killed the
  container's `sleep infinity` keep-alive (process 3, under `tini`). A stand-in must print what it would run,
  never run it. Any kill inside a sandbox must name the processes exactly, never `sleep` or `claude` by bare name.
