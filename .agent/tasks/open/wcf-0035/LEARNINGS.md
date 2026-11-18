# Learnings

- 2026-11-17 [sandbox] — A dry run of an sbx probe, with a stand-in `sbx` whose `env exec` ran its command locally,
  killed this planner's own sandbox: `pkill -x claude` killed Claude Code, and `pkill -x sleep` killed the
  container's `sleep infinity` keep-alive (process 3, under `tini`). A stand-in must print what it would run,
  never run it. Any kill inside a sandbox must name the processes exactly, never `sleep` or `claude` by bare name.
- 2026-11-17 [testing] — The checks need `uv sync --group dev` first; plain `uv run pytest` fails with "Failed to spawn: pytest".
- 2026-11-17 [testing] — In the `checkouts` fixture the notes checkout is a worktree of the code checkout's clone, so pointing the code checkout's origin elsewhere changes the notes checkout's too.
- 2026-11-17 [testing] — To show a child's signal dispositions, read `/proc/self/status` from a non-Python child (grep): Python catches SIGINT at startup, so its own SigCgt always has it.
- 2026-11-18 [proposal] — code-review's "Spec, partial" bar makes every requirement need a test or a check. A Spec sub-agent marked composition-root lines (`run.main` printing and returning the status) as Blocking and suggested stubbing `launch`, which DR3 forbids. DR7 holds those lines by review. Proposal: have the Spec brief say that a composition root's output and exit-code lines are met by reading them in review (DR7).
- 2026-11-18 [proposal] — code-review's Names bar reports only names that mislead at a use or break an agreed word. That let
  private helpers through (`_CantTell`/`_cant_tell`, `_unsaved_work`, `_do_nothing`, `_checked_output`), and the human
  then ruled them Blocking (wcf-0035, round 3). Proposal: the Names bar also blocks a name, private ones included, that
  doesn't say what its thing holds or returns, or why it exists, and one phrase used for two different things across
  packages. Also: a Blocking finding the human adds in a review session shouldn't count toward the three-round limit
  that sends a task to `no-agreement`.
- 2026-11-18 [testing] — To check a test pins a refactor, back up the edited file before a mutation: `git checkout -- <file>`
  to undo the mutation also drops the uncommitted fix. Commit the fix first, or restore from a copy.
- 2026-11-18 [proposal] — The `code-review` skill always runs five sub-agents, even for a round the human limits to one small fix, such as round 5 here: six lines in one function. I reviewed that round inline instead. Proposal: let a fix round whose diff changes one or two functions be reviewed inline on all five axes, saying so in the round.
