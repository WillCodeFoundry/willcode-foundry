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

## 2 · planner · progress
Done: the human ran the sbx probe twice on sbx v0.46.0, each time in a throwaway sandbox without foundry's kit:
- U1: after the agent run ends, the sandbox stays running.
- U2: local sbx has no detach; `--detach-keys` and `sbx attach` are cloud-only.
- U3: `sbx run` exits 0 whether the human `/exit`s or Ctrl-C's out, so its exit code can't say how the run ended.
- U4: `sbx run` as a child process behaves as today. The first Ctrl-C only clears Claude Code's input, the parent never sees it, and the parent regains control after the run.
- U5: SIGHUP to `sbx run` kills it but leaves `claude` running in the sandbox, orphaned.
- U6: `sbx run --name X -- -p "<prompt>"` runs headless, prints the final message and returns by itself (exit 0, no claude left).
- U7: in `-p` mode, a Stop hook that blocks makes the agent continue, and the run returns once the hook allows the stop.
- Plain `-p` prints only the agent's last message, nothing while it works.
- The kit's managed settings already set `bypassPermissions`, so headless runs won't stall on prompts.
Next: the human answers round 4 (Q14–Q19):
- Q14: a live view of a headless run.
- Q15: each role's default mode.
- Q16: `--interactive`/`--headless` overrides.
- Q17: Ctrl-C stops the agent in the sandbox before the report.
- Q18: foundry killed goes under Risks.
- Q19: no time limit.
Then redraft wcf-0035 as slice 1.
