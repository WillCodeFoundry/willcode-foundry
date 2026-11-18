# Review: wcf-0035

## Round 1 (reviewing c21111b)

Reviewed against TASK.md at d7e8764 and PLAN.md at 8e44876.
- TASK.md's history holds only allowed, signed commits: 0c87bbf (the human's `Add task`), then 87494ff and d7e8764. The last two are signed by the identity the planner shares with the architect, so the planner's and the architect's changes can't be told apart.
- PLAN.md's history holds only commits signed by the dev's identity. The human approved it in the dev's session at 8e44876 (LOG entry 15), which ADR-0015 allows. It hasn't changed since.

Diff `42a04e8...c21111b`, four commits: d3c32ef, 9fb2b2c, 2a29fa9, c21111b. The host tier, ruff (check and format) and mypy pass, run in a throwaway clone. The sbx tier was not run, because there is no sbx here.

### Standards

DR2, DR3 and DR7 hold. ADR-0003 and ADR-0014 still read true. No doc still says foundry replaces itself or never learns how the run ended.

- **R1 · Follow-up.** `ARCHITECTURE.md:48` and `src/agent_runtime/claude_hooks.py:1` still say the module holds "the rules of the Claude hooks". session-check's rule now lives in `unsaved_work.py`. `claude_hooks.py:4-5` also retells that rule in its own words, against AGENTS.md's "Write each fact once". Who hits it: a dev changing the stop check who opens `claude_hooks.py` first. Codemap row 49 points them the right way. Direction: say guard-bash's rule, and point to `agent_runtime.unsaved_work` rather than retelling it. This shares a cause with R9.
- **R2 · Follow-up.** `agent-kit/AGENTS.md:301-302` tells every agent it can't stop while a checkout has "uncommitted or unpushed changes". Two things are wrong with that:
  - It leaves out AC8's block when origin can't be reached. The block's reason explains it, and the next stop goes through.
  - It uses "unpushed", which `GLOSSARY.md` now lists under Avoid.

  Direction: say "unsaved work, or when it can't tell".
- **R3 · Follow-up.** `ARCHITECTURE.md:9`'s summary still ends at "hands the terminal to sbx". The launch steps below it are right. Direction: add that foundry reports the checkout status when the run ends, or accept as is.

### Spec

| AC | Status | Code · test |
|---|---|---|
| AC1 | met | `check_unsaved_work.report`, `check_checkout_status` · `test_both_saved_is_one_line_and_exit_0`, `test_both_saved_is_the_command_s_output_and_exit_0`. `run.py:49-51` read in review, see R4. |
| AC2 | met | `describe_unsaved_work` · test_unsaved_work.py's uncommitted, not pushed and both cases; `test_any_other_exit_is_exit_1_with_the_command_s_stdout_then_stderr` |
| AC3 | met | `check_checkout_status`, `_has_commits_not_pushed` · test_launcher.py's stopped, agent running and failing-check cases; test_unsaved_work.py's origin, removed checkout and git-missing cases |
| AC4 | met (automated) | `SystemHost.run_in_terminal` · test_host.py's SIGINT, SIGKILL and handler-restored cases; `launcher.py:75-76` read in review. **By hand against real sbx: not yet done.** |
| AC5 | met (automated) | `provision_sandbox` · `test_a_running_agent_refuses_the_launch_before_anything_is_given_to_the_sandbox`, plus the `is_agent_running` and `stop_hint` tests. **By hand: not yet done.** |
| AC6 | met (automated) | `run_in_terminal` · `test_run_in_terminal_starts_the_child_with_the_default_interrupt_handler`, plus the attach tests. **By hand (Ctrl-C, resize): not yet done.** |
| AC7 | met | README "Use"; ARCHITECTURE launch steps 4–5 |
| AC8 | met | `_has_commits_not_pushed` · `test_a_stop_is_blocked_when_origin_can_t_be_reached`, `test_a_stop_caused_by_this_hook_blocking_goes_through` |

The code matches PLAN.md's names, seams, approach and every message text. There is no scope creep. The edit to `docs/security-model.md` is outside PLAN.md's Docs list, but it only records AC8.

- **R4 · Follow-up** (downgraded from Blocking by the reviewer). Nothing tests that `run.main` prints the status on stderr and returns its exit code (`src/foundry/commands/run.py:49-51`). Nothing tests that `launch` goes from attach to the check either (`src/foundry/agent_sandbox/launcher.py:75-76`).
  - Both are composition roots. DR7 lets one turn a result into output and an exit code, and holds that by review. I read those lines and they do what AC1, AC2 and AC4 say.
  - The sub-agent's suggested fix, stubbing `agent_sandbox.launch`, would patch, which DR3 rules out.
  - The by-hand AC4 check in PLAN.md's Tests covers the whole path.

  Direction: accept as is.
- **R5 · Follow-up.** A checkout gets one reason only (`src/agent_runtime/unsaved_work.py:37-43`). Uncommitted changes in a checkout whose origin can't be reached show only as "can't tell: origin can't be reached". The exit code is still 1. Saying both would need wording PLAN.md's Errors doesn't have. Direction: accept as is.

### Behaviour

The host tier, ruff and mypy pass. These were checked and didn't fail:
- detached HEAD;
- a branch never pushed, which session setup prevents;
- the next stop going through after a block;
- the SIGINT handler put back on an exception, and the child starting with the default handler;
- a SandboxError after attach becoming "can't tell";
- `pgrep -x claude` matching only Claude Code;
- the check running as the agent user.

- **R6 · Follow-up.** Any failed `git fetch origin <branch>` is labelled "origin can't be reached" (`src/agent_runtime/unsaved_work.py:56`). That includes a branch deleted on origin, such as GitHub's auto-delete after the PR is merged, followed by a run before the task is closed. Reproduced with a local bare origin. Nothing is lost: it is still "can't tell", exit 1. But the agent and the human are given the wrong reason. This is rare. Direction: don't claim the network is down when git says the ref is missing, or accept as is.

### Smells

These functions are clean or new with no finding:
- `describe_unsaved_work`, `_has_commits_not_pushed`, `_first_line`;
- `check_unsaved_work.main` and `report`;
- `claude_hook.session_check`, `__main__.COMMANDS`;
- `Host.run_in_terminal`, `SystemHost.run_in_terminal`, `_do_nothing`;
- `launch`, `check_checkout_status`, `_cant_tell`, `provision_sandbox`, `CheckoutStatus`;
- `Sandbox.is_running`, `is_agent_running`, `stop_hint`, `attach`, `_sandbox_statuses`, and `list_live_sandboxes`, which is simpler now;
- `run.main`, `cli.main`, `Session.launch_request`;
- every new or changed test except those in R7, and `FakeHost`.

`_unsaved_work` and `_checked_output` have R8, `test_a_removed_checkout_is_can_t_tell` and `test_git_missing_is_can_t_tell` have R7, and the `claude_hooks.py` docstring and `FakeSandbox` have R9.

- **R7 · Blocking.** Possible Duplicated Code, the same behaviour tested twice.
  - `tests/agent_runtime/test_unsaved_work.py:109` (a removed checkout) and `:121` (git missing) test, through `report`, the same `describe_unsaved_work` branches that `:187` and `:197` test through `session_check`.
  - Any change that breaks one breaks its twin.
  - CONTRIBUTING.md:61 says "Each behaviour is tested once". The next dev who rewords "can't read it" edits four tests.
  - Direction: keep one test of each case. This isn't a plan change: both seams stay tested, by the other cases.
- **R8 · Blocking.** Possible Duplicated Code, one wording built in two places. `src/agent_runtime/unsaved_work.py:43` adds the "can't read it:" prefix for a `GitError`, and `:67` builds the same prefix into `_CantTell`'s message. At the fixed point, one `except` handled both. The next dev who rewords a reason has to find both. Direction: put the "can't read it" wording in one place.
- **R9 · Follow-up.** Two small things:
  - `src/agent_runtime/claude_hooks.py:4-7`'s "Both are guardrails… Both trust the environment" narrates a rule this module no longer holds. This shares a cause with R1.
  - `tests/agent_sandbox/conftest.py:113` gives a stop hint naming `fake` for a sandbox named `n`, so the assertions read "sandbox n …; `sbx stop fake`".

  Direction: accept as is, or take the hint's name from the sandbox.

### Names

No findings. Every name the diff adds matches PLAN.md's Names and GLOSSARY.md, and none misleads at a use. That includes the glossary terms "Unsaved work" and "Checkout status", every new test name, and the fakes' new attributes. Three were checked closely and pass:
- `is_agent_running`, which starts a stopped sandbox, but both callers run it only on a running one;
- "launcher" in `__main__.py:33`, which follows existing wording;
- `_sandbox_statuses`.

### Still for the human

Run these by hand against real sbx, as PLAN.md's Tests lists them:
- AC4: `kill` the `sbx run`, then read the report.
- AC5: start a second `foundry run` beside a running one.
- AC6: one Ctrl-C only clears the input, and resizing works.
- The sbx tier, `uv run pytest -m sbx`.

Summary: Standards 3 (0 Blocking; worst R2, the agent's instructions omit AC8's block). Spec 2 (0 Blocking; worst R4, the composition-root lines untested, accepted under DR7). Behaviour 1 (0 Blocking; R6, the wrong reason for a deleted branch). Smells 3 (2 Blocking; worst R7, a duplicated test). Names 0. No design questions.

Verdict: changes needed

## Round 2 (reviewing 4c6ebc2)

Reviewed against TASK.md at d7e8764 and PLAN.md at 8e44876.
- Neither file's history has changed since round 1. TASK.md's last two commits are signed by the identity the planner shares with the architect.
- LOG.md has no change decided by the human that TASK.md is missing. Entries 23–24 record checks the human ran by hand, not decisions.

Fix diff `c21111b...4c6ebc2`, two commits: 02e6baf and 4c6ebc2. In a throwaway clone these all pass: the host tier, ruff (check and format), mypy, vulture and pylint (10.00). The human ran the sbx tier against real sbx v0.46.0 and it passed, 10 tests (LOG entry 23).

### Earlier findings
- **R1: closed** (4c6ebc2). `claude_hooks.py:1` and `ARCHITECTURE.md:48` now name guard-bash's rule. They point to `agent_runtime.unsaved_work` rather than retelling session-check's rule.
- **R2: closed** (4c6ebc2). `agent-kit/AGENTS.md:301-303` says "unsaved work, or when it can't tell, such as when origin can't be reached", and no longer says "unpushed".
- **R3: closed** (4c6ebc2). `ARCHITECTURE.md:9` adds that foundry reports the checkout status when the agent run ends.
- **R4: deferred**, as the dev answered. DR7 holds these lines by review. The human's AC4 check by hand now also covers the path from attach to the report (LOG 23–24).
- **R5: deferred**, as the dev answered.
- **R6: deferred**, as the dev answered.
- **R7: closed** (02e6baf). A removed checkout and git missing are each tested once, through `check_unsaved_work.report`, at `tests/agent_runtime/test_unsaved_work.py:109` and `:121`.
- **R8: closed** (02e6baf). "can't read it:" is built only at `src/agent_runtime/unsaved_work.py:43`.
- **R9: closed** for the docstring (4c6ebc2). The fake's stop hint is deferred, as the dev answered.

### Standards
R1–R3 are closed. There are no new findings.
- The rewritten docstrings and docs agree with the code and with `docs/security-model.md`.
- `commands/claude_hook.py:3` still reads true.
- `GitError`'s docstring (`git.py:28`) fits its new use in `_checked_output`.

### Spec
There are no new findings. The two tests R7 removed duplicated cases that are still tested through the checkout status, so every criterion is still shown met.

| AC | Status | Code · test or check |
|---|---|---|
| AC1 | met | `check_unsaved_work.report`, `run.main` · `test_both_saved_is_one_line_and_exit_0`, `test_both_saved_is_the_command_s_output_and_exit_0`. By hand: `/exit` with both checkouts saved exited 0 (LOG 23). |
| AC2 | met | `describe_unsaved_work` · test_unsaved_work.py's uncommitted, not pushed and both cases |
| AC3 | met | `_unsaved_work`, `check_checkout_status` · test_unsaved_work.py:95, :109 and :121; test_launcher.py's stopped-sandbox, running-agent and failing-check cases |
| AC4 | met | `SystemHost.run_in_terminal` · test_host.py. By hand: after SIGTERM to `sbx run`, foundry printed "can't tell", because an agent was still running, and exited 1 (LOG 23–24). |
| AC5 | met | `provision_sandbox` · `test_a_running_agent_refuses_the_launch_…`. By hand: the refusal named the sandbox and gave `sbx stop`, exited 1, and the first agent kept running (LOG 23). |
| AC6 | met | `run_in_terminal` · `test_run_in_terminal_starts_the_child_with_the_default_interrupt_handler`. By hand: one Ctrl-C only cleared the input, and resizing redrew the UI (LOG 23). |
| AC7 | met | README "Use", ARCHITECTURE.md launch steps; unchanged by the fixes |
| AC8 | met | `_has_commits_not_pushed` · test_unsaved_work.py:179 and :190 |

### Behaviour
R8 is closed. There are no new findings.
- I compared the old (c21111b) and new (4c6ebc2) `_unsaved_work` with a stub `Git`. They give the same message in all six cases: status failing, rev-list failing, fetch failing, and git missing at status, fetch or rev-list.
- `_CantTell` and `GitError` don't inherit from each other, so the order of the two `except`s changes nothing. No new exception type can escape `describe_unsaved_work`.

### Smells
R7, R8 and R9 are closed. There are no new findings.
- `unsaved_work.py:_checked_output` is clean, and simpler than at c21111b: it no longer carries its caller's wording.
- The `claude_hooks.py` module docstring is clean.
- Removing the two tests adds no smell.
- `_unsaved_work` is unchanged since c21111b.

### Names
There are no findings.
- `GitError` in `_checked_output` is clean.
- These prose terms are clean, each in the glossary's sense: "guard-bash's rule", "session-check's rule", "the git hooks' rules", "checkout status", "agent run", "unsaved work", "can't tell" and "the block's reason".
- The fix removes the _Avoid_ word "unpushed" from `agent-kit/AGENTS.md`.
- The messages match PLAN.md's Errors exactly.

Summary: Standards 0, Spec 0, Behaviour 0, Smells 0, Names 0 new findings. No new finding blocks, and no design question is open. Round 1's Blocking findings, R7 and R8, are closed. R4, R5, R6 and half of R9 are deferred as follow-ups.

Verdict: approved
