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

## 8 · dev · progress
Done: in the dev's session, the human chose `sbx stop <name>` as the command the refusal (AC5) and the "agent still running" report give, over `pkill -TERM -x claude` through `sbx env exec`. Its reasons: it takes only the name, needs no socket, and matches no process by name. PLAN.md amended to match: `Sandbox.stop_command`. Also added to "Approach" why the report doesn't reuse `claude-hook session-check`.
Next: the human is reviewing PLAN.md in this session; plan-ready stands until they approve or ask for changes.

## 9 · dev · progress
Done: decisions by the human in this session, folded into PLAN.md:
- The runtime prints the exit report's lines itself, as plain text, and its exit code says saved (0) or not (1). No JSON, no record in `contract.py`, no report module in foundry.
- The runtime command is named `check-unsaved-work`.
- The stop check uses the report's wording, with each checkout's dir and branch. It blocks exactly when it did; the human ruled the new wording within OS1.
- Also cut: `attach_and_check`, new `sbx ls` parsing (`list_live_sandboxes` is reused), `Host.exec`, and the unused test fake `Attached`.
Next: the human reviews PLAN.md, its names first.

## 10 · dev · progress
Done: PLAN.md amended: the stop check and the report share `claude_hooks.unsaved_work` with no mode; a failed fetch is "can't tell" for both.
- Asks D1 → planner: change OS1 so the stop check also blocks when origin can't be reached, instead of comparing with the last fetched state. Its reason says "can't tell: origin can't be reached". The agent's next stop still goes through, as after any block. Why: one definition with no mode parameter; the stop check already blocks when it can't read a checkout; DR6 says a hook that enforces a rule blocks when it can't check it. Cost: one extra stop for an agent whose work was saved, when GitHub is unreachable.
- Answers D1: yes, change OS1 that way (the human).
Next: the human goes on reviewing PLAN.md in this session. TASK.md doesn't hold D1 yet, so the turn ends with task-question for the planner to fold it in, unless the human says otherwise.

## 11 · dev · progress
Done: PLAN.md amended, as the human decided: `unsaved_work` moves from `claude_hooks.py` to its own runtime module, `agent_runtime/unsaved_work.py`. `ExitReport` keeps its name in `agent_sandbox` (the human).
Next: the human's answer on a follow-up for a check-only command, then the rest of their review.

## 12 · dev · progress
Done: the human agreed to a follow-up for a check-only command, and said the planner will fold D1 into TASK.md.
- Follow-up: foundry run (src/foundry/commands/run.py) · the exit report exists only at the end of a `foundry run`; there is no command to see it without starting an agent · after `sbx stop`, or while an orphaned agent runs, the human can't learn whether work is unsaved until the next agent run ends.
Next: the human's review of PLAN.md's names, starting with `launcher.exit_report`.

## 13 · dev · progress
Done: PLAN.md amended: `ExitReport` is now `CheckoutStatus`, and `exit_report` is now `check_checkout_status`, as the human decided.
- Asks D2 → planner: rename TASK.md's term "Exit report" to "Checkout status": what `foundry run` reports after an agent run ends: each checkout's unsaved work, that both are saved, or why it can't tell. It names what is checked, both checkouts, after `git status`, rather than when, so a later check-only command can share it.
- Answers D2: yes (the human).
Next: the human double-checks the plan's other names.

## 14 · dev · progress
Done: PLAN.md amended, the human's name review:
- `LaunchRequest.after_run_command` is now `checkout_status_command`.
- `claude_hooks.unsaved_work` moves as `unsaved_work.describe_unsaved_work`.
- `Sandbox.is_running` requires sbx's status to be exactly "running", sharing `sbx ls --json`'s parsing with `list_live_sandboxes`.
- The human kept `check-unsaved-work` and `CheckoutStatus.text`.
Next: the human's approval of PLAN.md.

## 15 · dev · task-question
Done: plan-approved (the human) at 8e44876. The human reviewed PLAN.md in this session, its Shape and Names included, so it replaces the plan round. No code yet.
- D1 and D2 (entries 10 and 13) are decided by the human but not yet in TASK.md: OS1 changes so the stop check also blocks when origin can't be reached, and the term "Exit report" becomes "Checkout status".
Next: the planner folds D1 and D2 into TASK.md. Then the dev implements PLAN.md from step 1, with no further plan round.

## 16 · planner · progress
Done: folded the human's decisions into TASK.md:
- Answers D1: OS1 can only rule things out, so the new behaviour is a criterion, AC8: when origin can't be reached, the stop check blocks with "can't tell", and the agent's next stop goes through. OS1 now leaves every other change to when the stop check blocks out of scope. Both lines end `Amended: D1`.
- Answers D2: the term "Exit report" is now "Checkout status", in "Terms" and the Goal, marked `Amended: D2`.
- Also: entry 12's follow-up (a check-only command) is OS7, and "Risks" no longer says no follow-up touches this code.
Next: end the turn, planned.

## 17 · planner · planned
Done: TASK.md holds D1 and D2 (d7e8764): AC8 and the narrowed OS1 for D1, the term "Checkout status" for D2, and OS7 for entry 12's follow-up. Open questions is empty.
Next: the dev implements PLAN.md from step 1. The human approved the plan at 8e44876 (entry 15), so no further plan round.

## 18 · dev · progress
Done: merged origin/HEAD (already up to date). PLAN.md step 1 in d3c32ef: `agent_runtime/unsaved_work.py` with `describe_unsaved_work`, the new wording, "can't tell" when origin can't be reached (AC8), and the runtime command `check-unsaved-work`. Stop-check tests moved to `tests/agent_runtime/test_unsaved_work.py`; `tests/agent_kit/test_stop_hook.py` runs the built command.
Next: PLAN.md step 2: `Host.run_in_terminal`, `Sandbox.is_running`, `is_agent_running`, `stop_hint`; `attach` waits.

## 19 · dev · ready-for-review
Done: PLAN.md steps 1–6, in d3c32ef, 9fb2b2c, 2a29fa9 (sbx test) and c21111b on task/wcf-0035. Draft PR: https://github.com/WillCodeFoundry/willcode-foundry/pull/87, CI passes. No plan amendments. The criteria, each with its test:
- AC1: `test_both_saved_is_one_line_and_exit_0` (tests/agent_runtime/test_unsaved_work.py); `test_both_saved_is_the_command_s_output_and_exit_0` (tests/agent_sandbox/test_launcher.py); `test_check_unsaved_work_says_both_are_saved_then_names_unsaved_work` (tests/agent_kit/test_stop_hook.py).
- AC2: test_unsaved_work.py's uncommitted, not pushed, and both-in-both-checkouts cases; `test_any_other_exit_is_exit_1_with_the_command_s_stdout_then_stderr` (test_launcher.py).
- AC3: test_launcher.py's stopped sandbox (nothing run in it), agent still running, failing check; test_unsaved_work.py's origin out of reach, removed checkout, git missing.
- AC4: test_host.py's `run_in_terminal` interrupt and SIGKILL cases, and the handler put back. By hand against real sbx: NOT done (no sbx here).
- AC5: `test_a_running_agent_refuses_the_launch_before_anything_is_given_to_the_sandbox` (test_launcher.py); test_sandbox.py's `is_agent_running` and `stop_hint` cases. By hand: NOT done.
- AC6: `test_run_in_terminal_starts_the_child_with_the_default_interrupt_handler` (test_host.py); test_sandbox.py's attach cases. By hand (Ctrl-C, resize): NOT done.
- AC7: README.md "Use", ARCHITECTURE.md launch steps 2, 4 and 5; tests/test_docs.py passes.
- AC8: `test_a_stop_is_blocked_when_origin_can_t_be_reached` and `test_a_stop_caused_by_this_hook_blocking_goes_through` (test_unsaved_work.py).
- The sbx tier's new `test_after_a_launch_with_no_agent_run_both_checkouts_are_saved` (tests/sbx/test_smoke.py) was not run: no sbx in this sandbox.
Next: the reviewer's code round. The human should run `uv run pytest -m sbx` and the by-hand checks for AC4–AC6 that PLAN.md's "Tests" lists.

## 20 · reviewer · progress
Done: TASK.md's and PLAN.md's histories hold only allowed, signed commits. TASK.md at d7e8764 is signed by the identity the planner shares with the architect. PLAN.md was approved by the human at 8e44876 (entry 15, allowed by ADR-0015), unchanged since. D1 and D2 are in TASK.md. No human-decided change is waiting.
Next: code round 1 on task/wcf-0035 at c21111b, five axes, written to REVIEW.md.

## 21 · reviewer · changes-needed
Done: code round 1 on c21111b, in REVIEW.md. Two findings are Blocking, both small and in `agent_runtime`:
- R7: a removed checkout and git missing are each tested twice, through `report` and `session_check`.
- R8: "can't read it" is built in two places in `unsaved_work.py`.

There are seven follow-ups, R1–R6 and R9. The ones directed "accept as is" need no change. All criteria are met in code and tests, but the by-hand checks for AC4–AC6 and the sbx tier still wait for the human.
- Follow-up: tests/agent_kit/test_stop_hook.py:82, tests/agent_runtime/test_unsaved_work.py:145 · test names say "unpushed work", now on GLOSSARY.md's Avoid list · a search for "unsaved work" misses them.
- Follow-up: tests/agent_runtime/test_unsaved_work.py:187 `test_a_stop_is_blocked_when_a_checkout_cant_be_checked` · spells `cant` and "can't be checked" beside `can_t_tell` tests · a search for `can_t_tell` misses it.
- Follow-up: src/foundry/agent_sandbox/sandbox.py:165 `list_live_sandboxes` · "live" counts "starting", next to `is_running`, which doesn't · a reader may take the two as one test.
- Follow-up: src/foundry/agent_sandbox/launcher.py:62 and :86 · the sandbox's name is read from `SandboxDefinition` once per caller · giving `Sandbox` its name would remove the second read.
Next: the dev answers R7 and R8, each test-first, and says for each follow-up whether it fixes, accepts or defers it.

## 22 · dev · ready-for-review
Done: merged origin/HEAD (already up to date). Answered round 1 on task/wcf-0035 at 4c6ebc2; host tier, ruff, mypy, vulture and pylint pass, and PR #87's CI passes. No plan amendments.
- Answers R7: fixed in 02e6baf. Kept the check-unsaved-work tests of a removed checkout and git missing, which PLAN.md's Tests and entry 19 cite for AC3, and removed their session-check twins. That also removes the `cant` test name in entry 21's second follow-up.
- Answers R8: fixed in 02e6baf. `_checked_output` raises GitError without the prefix, and `_unsaved_work`'s one `except GitError` adds "can't read it:". Messages unchanged; the existing tests pin them.
- Answers R1: fixed in 4c6ebc2. `claude_hooks.py`'s docstring and its codemap row now say guard-bash's rule, and point to `agent_runtime.unsaved_work` for session-check's.
- Answers R2: fixed in 4c6ebc2. `agent-kit/AGENTS.md` says the agent can't stop with unsaved work, or when it can't tell, such as origin out of reach.
- Answers R3: fixed in 4c6ebc2. ARCHITECTURE.md's bird's-eye view adds that foundry reports the checkout status when the run ends.
- Answers R4: deferred, because DR7 holds composition roots by review, and the by-hand AC4 check covers the path.
- Answers R5: deferred, because saying both reasons needs wording PLAN.md's Errors lacks, and the exit code is already 1.
- Answers R6: deferred, because telling a deleted branch from an unreachable origin means parsing git's stderr, a new message outside PLAN.md's Errors; the result is still "can't tell", exit 1.
- Answers R9: fixed in 4c6ebc2 for the docstring, with R1. The fake's stop hint is deferred, because `FakeSandbox` doesn't hold its name and the tests read fine.
- Criteria: as entry 19 ticks them, with AC3's removed-checkout and git-missing cases now tested once each, through check-unsaved-work.
- Still for the human, by hand against real sbx: AC4 (kill `sbx run`, then read the report), AC5 (a second `foundry run` beside a running one), AC6 (one Ctrl-C only clears the input; resize), and `uv run pytest -m sbx`.
Next: the reviewer's round 2.

## 23 · dev · progress
Done: the human ran the by-hand checks against real sbx (v0.46.0) at 4c6ebc2, on a throwaway task, foundry-test sbx-0002, with the planner, using a guided script from this dev session's workspace dir. All passed:
- AC6: one Ctrl-C only cleared the input and the agent went on; resizing redrew the UI.
- AC1: after `/exit` with both checkouts saved, the status printed, and `foundry run` exited 0.
- AC5: a second `foundry run` while the agent ran printed "error: an agent is already running in sandbox planner-foundry-test-sbx-0002, so no second one is started; stop it with `sbx stop planner-foundry-test-sbx-0002`", exited 1, and the first `sbx run` stayed alive.
- AC4: SIGTERM to the host's `sbx run` ~30s after attach. foundry survived, printed a report, and exited 1. The report's exact text wasn't captured.
- The sbx tier, `uv run pytest -m sbx`: 10 passed.
- The sandbox was stopped with `sbx stop`, and sbx-0002 closed.
Next: the reviewer's round 2. Nothing is left for the human by hand.

## 24 · dev · progress
Done: the human confirmed AC4's report, which entry 23 left uncaptured: after the SIGTERM to `sbx run`, it said "can't tell" because an agent was still running in the sandbox, as probe O1 (entry 3) predicted.
Next: the reviewer's round 2.

## 25 · reviewer · approved
Done: code round 2 on 4c6ebc2, in REVIEW.md.
- TASK.md (d7e8764) and PLAN.md (8e44876) are unchanged since round 1. No decision by the human is waiting to go into TASK.md, and no design question is open.
- Closed: R1, R2, R3, R7, R8, and R9's docstring.
- Deferred, as the dev answered: R4, R5, R6, and R9's fake stop hint.
- No new findings on any of the five axes.
- All eight criteria are met. For AC4–AC6, the human's checks by hand against real sbx (entries 23–24) count as met.
- Host tier, ruff, mypy, vulture and pylint pass at 4c6ebc2.
- Follow-up: src/agent_runtime/unsaved_work.py:31 `_CantTell` · since 02e6baf only a failed fetch raises it, while a failed git command reaches "can't tell" through `GitError` · its name and docstring promise every can't-tell case, so `_unsaved_work` keeps two `except`s that each write "can't tell: …".
Next: the dev opens PR #87 for the human (pr-ready).

## 26 · reviewer · changes-needed
Done: code round 3 on 4c6ebc2, in REVIEW.md. After round 2, the human asked which names the dev introduced that they might not like, and ruled four of them Blocking:
- R10: `_CantTell` and `_cant_tell`;
- R11: `_unsaved_work`;
- R12: `_do_nothing`;
- R13: `_checked_output`, a near-copy of `Git.output`.

This round replaces round 2's approval. Entry 25's follow-up on `_CantTell` is now part of R10.

Round 3 is the third code round. The human chose these findings in this session and wants them fixed, so the task goes back to the dev rather than to `no-agreement`.
Next: the dev fixes R10–R13, each test-first. For R13: if the fix changes the "can't read it" message, amend PLAN.md's Errors, and get a plan round, before the code changes.

## 27 · dev · plan-ready
Done: merged origin/HEAD (already up to date; code unchanged since 4c6ebc2). R10, R11 and R13 all land on `unsaved_work.py`, and R13 changes PLAN.md's Errors, so, as ROLE.md says when findings cluster, I revised that part of PLAN.md (at b13bcee) instead of patching. No code yet.
- Answers R10: plan amended. `_CantTell` becomes `_ComparisonFailure`, raised only by `_compare_with_origin` (was `_has_commits_not_pushed`), which wraps every GitError in it; `_describe_checkout` is the one place that writes "can't tell". `launcher._cant_tell` becomes `_unknown_status`.
- Answers R11: plan amended. `_unsaved_work` becomes `_describe_checkout`.
- Answers R12: plan amended. `_do_nothing` becomes `_outlive_interrupt`.
- Answers R13: plan amended. `_checked_output` goes. Left open as a judgement call for the human, in Approach: A (recommended) uses `Git.output`'s wording, `can't read it: git -C <dir> status --porcelain failed: <git's stderr>`, which may run over several lines; B keeps today's wording with a helper named for what differs.
Next: a plan round on PLAN.md's round-3 revision, with the human choosing A or B for R13. Then the dev makes the changes, test-first for R13's message.

## 28 · dev · progress
Done: the human's review of the round-3 names, PLAN.md amended at f996a5e:
- `_ComparisonFailure` is now `_OriginComparisonFailure`: it names what the checkout is compared with.
- `_outlive_interrupt` is now `_outlive_interrupt_handler`: it says it is a signal handler. "ignore" stays out, because the handler isn't SIG_IGN, which PLAN.md turns down (R12).
Next: the human approves PLAN.md and chooses option A or B for R13, or the reviewer's plan round does.

## 29 · dev · progress
Done: the human chose option A for R13: a failed git command is worded as `Git.output` words it, `can't read it: git -C <dir> status --porcelain failed: <git's stderr>`.
Next: the human approves PLAN.md, or the reviewer's plan round does.

## 30 · dev · progress
Done: plan-approved (the human) at f4ead80. The human reviewed the round-3 revision in this session, its names and the R13 choice (option A) included, so it replaces the plan round.
Next: R13 test-first (the message), then the renames for R10, R11 and R12.

## 31 · dev · ready-for-review
Done: round 3 fixed on task/wcf-0035 at e38eec1, as PLAN.md's round-3 revision (approved by the human, entry 30) says. Host tier with coverage, ruff, mypy, vulture and pylint pass; PR #87's CI passes. No change to TASK.md waits.
- Answers R10: fixed in eb887f6 and e38eec1. `_CantTell` is `_OriginComparisonFailure`, raised only by `_compare_with_origin`, which wraps every GitError; `_describe_checkout` alone writes "can't tell". `launcher._cant_tell` is `_unknown_status`.
- Answers R11: fixed in eb887f6. `_unsaved_work` is `_describe_checkout`.
- Answers R12: fixed in e38eec1. `_do_nothing` is `_outlive_interrupt_handler`.
- Answers R13: fixed in eb887f6. `_checked_output` is gone; git commands use `Git.output`, and its wording (option A). `test_a_removed_checkout_is_can_t_tell` pins it, written first and seen failing.
- Criteria: as entries 19 and 22 tick them, each with the same test; AC4–AC6 by hand, entries 23–24. Behaviour changed only in R13's message, so those by-hand checks still hold.
Next: the reviewer's round 4, on e38eec1.

## 32 · reviewer · no-agreement
Done: code round 4 on e38eec1, in REVIEW.md. TASK.md (d7e8764) and PLAN.md (f4ead80, approved by the human) are unchanged. No decision by the human is waiting to go into TASK.md, and no design question is open.
- Closed: R10, R11, R12 and R13, the human's round-3 findings, on all five axes.
- New, Blocking: R14. `_compare_with_origin` splits "a failed fetch is can't tell" across a guard at `unsaved_work.py:56` and a raise after the `try` at `:62-63`. eb887f6 introduced the split. The fix is local: raise right after the failed fetch, inside the `try`.
- New, Follow-up: R15. A "can't read it" reason can run over several lines when the local branch is missing. That is option A's wording, which the human chose, so I direct accept as is.
- This is past the third code round, so the task goes to the human rather than back to the dev.
- Asks R14 → human: R14 is a small Blocking smell found in round 4, after the three-round limit. The dev hasn't answered it yet, so we don't disagree; only the round limit stops it going back. Should the dev fix it in one more round, or do you accept it as is, so the dev opens PR #87 (pr-ready)?
- Follow-up: src/foundry/agent_sandbox/host.py:50-51 `run_in_terminal` docstring · says "a handler that does nothing", what R12's rename moved away from · a reader learns what the handler does, not why.
- Follow-up: src/agent_runtime/unsaved_work.py:67 `_first_line` · the fetch's reason keeps git's first line, but `Git.output`'s reason keeps all of stderr · two styles of git error in one family of messages.
- Follow-up: src/agent_runtime/unsaved_work.py:24 loop variable `checkout` · holds a checkout's dir, beside `*_checkout_dir` · reads as a checkout, not a path.
Next: the human answers R14. If they accept it, the dev opens PR #87 (pr-ready). If they want it fixed, the dev fixes it test-first and the reviewer runs round 5 on that fix only.

## 33 · reviewer · changes-needed
Done: the human answered R14 in this session.
- Answers R14: one more round. The dev fixes R14, and the reviewer reviews only that fix (the human).
- Round 4's verdict stands: changes needed. R15 and entry 32's follow-ups need no change.
Next: the dev fixes R14 test-first: raise `_OriginComparisonFailure` right after the failed fetch, inside the `try` in `_compare_with_origin`, and drop the guard at `unsaved_work.py:56`. Then the reviewer runs round 5 on that fix only.
