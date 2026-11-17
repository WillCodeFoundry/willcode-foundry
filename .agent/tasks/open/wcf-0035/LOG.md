# Log

## 1 · planner · progress
Done: scoped the human's request: "when an agent finishes, tell me whether it left unsaved work, and where, or why it can't tell". A first draft reported unsaved work when `sbx run` returns. The human pointed out that the agent can't end its own agent run, so in practice it only returns on the human's `/exit`. Direction agreed in discussion, not yet a TASK.md:
- Roles can run headless (Claude Code `-p` through `sbx run`), so the run ends when the agent stops. The Stop hook still makes it save its work first.
- The mode is a default per role in `config/foundry.yaml`, like `model` (ADR-0014), with a `foundry run` flag to override it for one launch. The planner, and any launch where the human wants to talk, stays interactive.
- After every agent run, interactive or headless, foundry reports unsaved work in both checkouts, or why it can't tell, and exits 0 when saved and 1 otherwise.
- No resuming of a headless conversation: an agent records what it needs in the task notes. A human answers through `LOG.md`/handoff, or by launching the role interactively, which starts fresh from the notes.
- Starting the next role when a turn ends stays a later slice.
Next: the human runs `sbx-exit-probe.sh` (in the planner session's workspace dir, on the host) to settle these sbx facts:
- U1: is the sandbox still running after `sbx run` returns?
- U2: can `sbx run` detach?
- U3: exit code, and does it return only after Claude Code exits?
- U4: does Ctrl-C reach a parent process?
- U5: what does SIGHUP do?
- U6: does `-p` through `sbx run` stream its output and return by itself?
- U7: does a blocking Stop hook make `-p` continue?
Then redraft wcf-0035 as slice 1: headless mode plus the exit report. The plan goes to the architect, because it changes how an agent run is driven.
