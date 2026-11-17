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

## 3 · planner · progress
Done: the human ran probe round 3 (`sbx-probe-3.py`, sbx v0.46.0, throwaway sandbox):
- L1: `sbx run -- -p --output-format stream-json --verbose` with stdout piped (no tty) prints none of the agent's output: only a terminal-title escape at the end, exit 0.
- L2: under a pseudo-terminal it streams live, one JSON event per line as the agent works (each tool call within ~0.1s). But the output is mixed with sbx's own lines ("Attaching…", "Starting claude agent…", "Workspace: …") and escape sequences: a title set and a screen clear glued to the front of the first JSON line, a cursor/title reset at the end. Line endings are CRLF.
- O1: SIGINT, SIGTERM and SIGHUP to `sbx run` each end it (exit 1, 1, -1) and each leave the headless `claude` running in the sandbox.
- O2: the orphan keeps working and finishes its task. Some time after it finished, within 45s, the sandbox was found stopped, which never happened after a normal run. Cause not established.
- O3: an orphan shows in `ps` in the sandbox as `claude --dangerously-skip-permissions -p …` with parent pid 0. `pkill -TERM -x claude` through `sbx env exec` stops it and its tool's child processes within 5s, and the sandbox stays running.
Next: round 5 with the human:
- Q20: clean output via `sbx env exec`, to be probed, or a pty plus filtering?
- Q21: an interrupt stops the agent in the sandbox.
- Q22: refuse a launch when an agent is already running there.
Then redraft wcf-0035 as slice 1.

## 4 · planner · progress
Done: the human ran probe round 4 (`sbx-probe-4.py`, sbx v0.46.0, throwaway sandbox):
- L3: `sbx run -- -p --verbose` in text mode shows nothing until the final message (20s of silence). There is no live view without parsing.
- L4: `sbx env exec DIR -- sh -c 'cd <workspace> && claude --dangerously-skip-permissions -p --output-format stream-json --verbose "<prompt>"'`, piped, streams live: one JSON event per line as the agent works (system/init, assistant tool_use, user tool_result, …, result). stdout is pure JSON, stderr is empty, and credentials work (is_error false). This is the simplest live view: foundry reads the lines and prints its own.
- L5: SIGINT to that `sbx env exec` is ignored, even after 30s. After SIGKILL to it, no claude was left 3s later, but the agent's 40s sleep was due to end then too, so whether killing `env exec` takes the agent with it is unproven. A second `sbx env exec` (ps) ran fine while the first was running claude.
Next: round 5 with the human:
- Split: slice 1 is the exit report for today's interactive runs, plus refusing a launch while an agent runs. Slice 2 is headless mode with the live view and stopping on interrupt.
- Then approval of slice 1's TASK.md draft.

## 5 · planner · progress
Done: the human approved splitting the feature, "agent runs that end by themselves and report their unsaved work", into two slices. Slice 1 is this task. Slice 2 is a separate task the human will create with `foundry task create`, `After: wcf-0035`. Its planner starts from this scope, agreed with the human in this session:
- A role can run headless: its agent run ends by itself when the agent stops, and the Stop hook still makes it save first (probe U7, entry 2).
- Each role has a default mode in `config/foundry.yaml`, beside `model` (ADR-0014): planner and architect interactive, dev, reviewer and qa headless.
- `foundry run --interactive` or `--headless` overrides the mode for one launch.
- Headless runs use `sbx env exec <definition dir> -- claude -p --output-format stream-json --verbose "<opening prompt>"`, in the workspace. Probe L4 (entry 4) showed clean, live JSON on stdout.
- Text-mode `-p` shows nothing until the end (L3), and `sbx run` piped shows nothing at all (L1, entry 3).
- Live view: foundry prints one line per tool call and per agent message as they arrive, then the final message. No raw JSON.
- Ctrl-C during a headless run: `sbx env exec` ignores SIGINT (L5), so foundry stops the agent itself, as `pkill -TERM -x claude` in the sandbox did in probe O3 (entry 3), and then prints the exit report.
- No resuming a headless conversation. An agent records what it needs in the task notes. A human answers through LOG.md and `foundry task handoff`, or by launching the role interactively, which starts fresh from the notes.
- It reuses this task's exit report and its refusal to launch beside a running agent.
- Still open for that planner:
  - exactly what each live-view line shows;
  - the error for an unknown mode;
  - whether giving both flags is refused.
Next: write the turn's outcome.

## 6 · planner · planned
Done: TASK.md approved by the human and written. It has 7 criteria and 6 out-of-scope lines, and Open questions is empty. Slice 2's scope is in entry 5. The sbx facts behind the design are in entries 2–4. The probe scripts and their results sit in the planner session's workspace dir, on the host, not in the notes.
Next: the dev writes PLAN.md. The plan changes how foundry launches, from replacing itself to waiting for the agent, so it should go to the architect.

## 7 · dev · plan-ready
Done: merged origin/HEAD into task/wcf-0035 (already up to date; no code yet). Wrote PLAN.md. In short:
- foundry runs `sbx run` as a child and waits, instead of replacing itself.
- Then it checks, in order: the sandbox is running (`sbx ls`), no agent is running (`pgrep -x claude` in the sandbox), then runs a new runtime command, `unsaved-work`. That command prints each checkout's unsaved work as JSON, its format in `contract.py`.
- The stop check and `unsaved-work` share one definition, in a new `agent_runtime/unsaved_work.py`. They differ only on a failed fetch, which the stop check keeps tolerating (OS1).
- The same `pgrep` refuses a launch beside a running agent (AC5).
- AC4 (kill of `sbx run`) and AC6 (Ctrl-C, resize) need a check by hand against real sbx, as TASK.md's "Risks" says. PLAN.md's "Tests" names those steps.
Next: the reviewer's plan round. TASK.md's "Risks" asks that the plan go to the architect, since the launch changes from replacing itself to waiting for the agent.
