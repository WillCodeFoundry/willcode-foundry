# Task states follow a lifecycle written in code, checked at launch and guarded by content

A task's `STATE.json` on `agent-notes` says which state of its lifecycle it is in, and so whose turn it is. The lifecycles are a small Python table in `src/agent_runtime/task/lifecycles.py`, which foundry and the sandbox both import. The turn is checked once, by `foundry task run` on your machine. The only other check is `pre-commit`, which refuses a change to `STATE.json` that isn't committed alone, or isn't a legal transition for the role. Review rounds are limited by a sentence in the reviewer's `ROLE.md`, not by a counter.

## Considered options

- **Lifecycles as JSON in the kit, applied by a generic engine.** The engine existed twice, in the kit and on the host, held together by a parity test. It also needed a format validator and a contract test.
- **Turn checks in `session-setup`, `pre-push` and the Stop hook.** Three checks for one rule, each needing a fresh fetch and its own failure mode.
- **Telling hand edits apart by a commit trailer, a launch record or an environment variable.** Each is as easy to forge as the edit. Checking that the change itself is legal makes who wrote it irrelevant.
- **Counting review rounds, with a limit and a fallback state.** A field, a reset flag and a rule, for what one sentence does.
- **A Stop-hook check that the turn was ended.** It would fire at every question the planner asks while grilling, and a paused turn is normal. `foundry task list` shows a turn whose sandbox isn't running instead.
