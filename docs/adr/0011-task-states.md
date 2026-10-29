# Task states follow a lifecycle written in code, decided at launch and judged by one transition rule

A task's `STATE.json` on `agent-notes` says which state of its lifecycle it is in, from a Python table in `src/agent_runtime/task/lifecycles.py` that foundry and the sandbox share, and a test holds every lifecycle to its rules. The turn is decided once, by `foundry task run` on your machine, and the agent's task command only writes `STATE.json`, which the agent commits and pushes like any other note. One transition rule judges every change to it: the task command applies it before writing, and `pre-push` refuses a push whose change to `STATE.json` breaks it.

## Considered options

- **Lifecycles as JSON in the kit, applied by a generic engine.** The engine existed twice, in the kit and on the host, held together by a parity test. It also needed a format validator and a contract test.
- **Turn checks in `session-setup` and the Stop hook, beside the transition rule.** More checks for one rule, each needing a fresh fetch and its own failure mode.
- **Telling hand edits apart by a commit trailer, a launch record or an environment variable.** Each is as easy to forge as the edit. Checking that the change itself is legal makes who wrote it irrelevant.
- **Guarding `STATE.json`, and which notes a role may change, in `pre-commit`.** `revert`, `cherry-pick` and a commit on a detached HEAD get past it, and a fast-forward merge brings in commits it never saw. Every change reaches `origin` through a push, so `pre-push` judges what each push brings, and `pre-commit` is gone.
- **Judging the paths only by what a push leaves.** Notes added and removed again within one push would stay in the branch's history. So paths are judged in every pushed commit, and in what the push leaves, which covers a merge commit's own changes. `STATE.json` is judged by what the push leaves.
- **Requiring a change to `STATE.json` to be committed alone.** Checking it meant judging each pushed commit, not only the state before and after. A bundled change is still a legal one.
- **The task command committing and pushing `STATE.json` itself.** It needed a fast-forward, a commit, a push, and a reset when any of them failed, for what the agent already does with every other note.
- **Checking a lifecycle's rules when it is defined.** The lifecycles are constants the tests import, so a test catches a broken one as early, without an exception type and a rule engine.
- **Recording the state a task came from in `STATE.json`.** It repeated the last entry of the file's history, and `pre-push` had to keep it consistent.
- **Counting review rounds, with a limit and a fallback state.** A field, a reset flag and a rule, for what one sentence in the reviewer's `ROLE.md` does.
- **A Stop-hook check that the turn was ended.** It would fire at every question the planner asks while grilling, and a paused turn is normal. `foundry task list` shows a turn whose sandbox isn't running instead.

Source: #22.
