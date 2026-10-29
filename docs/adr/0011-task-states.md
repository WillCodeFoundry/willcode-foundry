# Task states follow a lifecycle written in code, checked at launch and guarded by content

A task's `STATE.json` on `agent-notes` says which state of its lifecycle it is in, from a Python table in `src/agent_runtime/task/lifecycles.py` that foundry and the sandbox share. The turn is checked once, by `foundry task run` on your machine. The only other check is `pre-push`, which refuses a push that changes `STATE.json` other than by a legal transition for the role.

## Considered options

- **Lifecycles as JSON in the kit, applied by a generic engine.** The engine existed twice, in the kit and on the host, held together by a parity test. It also needed a format validator and a contract test.
- **Turn checks in `session-setup`, `pre-push` and the Stop hook.** Three checks for one rule, each needing a fresh fetch and its own failure mode.
- **Telling hand edits apart by a commit trailer, a launch record or an environment variable.** Each is as easy to forge as the edit. Checking that the change itself is legal makes who wrote it irrelevant.
- **Guarding `STATE.json`, and which notes a role may change, in `pre-commit`.** `revert`, `cherry-pick` and a commit on a detached HEAD get past it, and a fast-forward merge brings in commits it never saw. Every change reaches `origin` through a push, so `pre-push` judges what each push brings, and `pre-commit` is gone.
- **Judging the paths only by what a push leaves.** Notes added and removed again within one push would stay in the branch's history. So paths are judged in every pushed commit, and in what the push leaves, which covers a merge commit's own changes. `STATE.json` is judged by what the push leaves.
- **Requiring a change to `STATE.json` to be committed alone.** Checking it meant judging each pushed commit, not only the state before and after. `bin/task` still commits it alone, and a bundled change is still a legal one.
- **Checking a lifecycle's rules when it is defined.** The lifecycles are constants the tests import, so a test catches a broken one as early, without an exception type and a rule engine.
- **Counting review rounds, with a limit and a fallback state.** A field, a reset flag and a rule, for what one sentence in the reviewer's `ROLE.md` does.
- **A Stop-hook check that the turn was ended.** It would fire at every question the planner asks while grilling, and a paused turn is normal. `foundry task list` shows a turn whose sandbox isn't running instead.

Source: #22.
