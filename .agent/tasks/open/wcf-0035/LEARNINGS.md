# Learnings

- 2026-11-17 [sandbox] — A dry run of an sbx probe, with a stand-in `sbx` whose `env exec` ran its command locally,
  killed this planner's own sandbox: `pkill -x claude` killed Claude Code, and `pkill -x sleep` killed the
  container's `sleep infinity` keep-alive (process 3, under `tini`). A stand-in must print what it would run,
  never run it. Any kill inside a sandbox must name the processes exactly, never `sleep` or `claude` by bare name.
- 2026-11-17 [testing] — The checks need `uv sync --group dev` first; plain `uv run pytest` fails with "Failed to spawn: pytest".
- 2026-11-17 [testing] — In the `checkouts` fixture the notes checkout is a worktree of the code checkout's clone, so pointing the code checkout's origin elsewhere changes the notes checkout's too.
- 2026-11-17 [testing] — To show a child's signal dispositions, read `/proc/self/status` from a non-Python child (grep): Python catches SIGINT at startup, so its own SigCgt always has it.
