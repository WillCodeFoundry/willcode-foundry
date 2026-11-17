# Plan: wcf-0035

## Approach
`foundry run` stops replacing itself with `sbx run`. It runs `sbx run` as a child on the same terminal, waits for it, then reports the checkout status. That takes three checks, in order, each stopping at the first that fails:

1. Is the sandbox running? Asked with `sbx ls --json`, through the existing `list_live_sandboxes`, which never starts it. Not running: "can't tell" (AC3).
2. Is an agent still running in it? Asked with `pgrep -x claude` through `sbx env exec`. Yes: "can't tell", with the stop hint (AC3).
3. The runtime's new `check-unsaved-work` command, run in the sandbox like `session-init`. It prints the report's lines itself, and exits 0 when both checkouts are saved, 1 otherwise (AC1–AC3).

foundry prints what the command printed, stdout then stderr, and exits 0 when it exited 0, 1 otherwise. A crash of the command shows its own error and exits 1. There is no format between the two programs but text and that exit code.

Step 2's check also runs before attaching, right after the sandbox is started, and refuses the launch when an agent is running (AC5). Its message gives `sbx stop <name>`, which stops the whole sandbox; the next launch starts it again. The human chose it over killing the agent's process (LOG entry 8).

The stop check and `check-unsaved-work` share one function, `unsaved_work`, moved from `claude_hooks.py` to its own module, `agent_runtime/unsaved_work.py`, since `check-unsaved-work` isn't a hook. They share one definition and one wording (TASK.md "Terms"). When `git fetch` fails, both say "can't tell: origin can't be reached" (AC3), so the stop check now blocks there too, where it compared with the last fetched state. Because: DR6, a hook that enforces a rule blocks when it can't check it, as the stop check already does when it can't read a checkout. An agent isn't stuck: its next stop goes through, as after any block. The human chose this, which changes OS1 (LOG entry 10, D1). The stop check's reason also gains each checkout's dir and branch, which the human ruled within OS1 (LOG entry 9).

While it waits, foundry swaps SIGINT's handler for one that does nothing, and puts the old one back after. A Ctrl-C that reaches foundry's process group, outside sbx's raw mode, then can't kill foundry before the report (AC4). The child starts with the default handler, since exec resets caught signals, so sbx and Claude Code see Ctrl-C as today (AC6). The child shares the terminal and process group, so it gets SIGWINCH as today (AC6).

Turned down:
- **foundry running the git commands itself through `sbx env exec`**, one call each. It gives the report a second definition of unsaved work, which TASK.md's "Terms" says the stop check and the report share.
- **Reusing `claude-hook session-check` after the run.** It speaks Claude Code's hook protocol: it reads a Stop event on stdin and prints a block decision. It doesn't give each checkout's dir and branch (AC2).
- **Keeping the stop check's offline behaviour (OS1 as first written)**, by a mode parameter or by two functions, one comparing with the last fetch. Either is more code for a case that costs an agent one more stop. The human chose to drop it (D1).
- **JSON from the runtime, read by foundry.** A record in `contract.py`, its JSON, and a module in foundry to word it: more code for the same lines. The human chose plain text (LOG entry 9).
- **`pkill -TERM -x claude` as the stop hint.** It needs the sandbox's socket in front of it, and it matches the agent by process name. The human chose `sbx stop` (LOG entry 8).
- **Reporting a failed `sbx ls` or `pgrep` after the run as an error.** AC3 asks for "can't tell" with the reason, so `check_checkout_status` turns `SandboxError` into one.
- **`SIG_IGN` while waiting.** The child inherits an ignored signal across exec, so Ctrl-C would stop reaching sbx. Breaks AC6.
- **Telling a running agent apart by `sbx ls`.** It lists sandboxes, not agents: a sandbox stays running after its agent run ends (probe U1, LOG entry 2).

Accepted: a sandbox that stops between `sbx ls` and the `env exec` after it would be started again by that call. The window is a fraction of a second.

## Shape

```
foundry.cli.main                                changed: docstring; no command replaces the process any more
└─ commands.run.main -> int                     changed: prints the checkout status on stderr, returns its exit code
   ├─ Session.launch_request                    changed: adds after_run_command, the runtime's `check-unsaved-work`
   └─ agent_sandbox.launch(request) -> CheckoutStatus   changed: attaches and waits, then returns the checkout status
      ├─ provision_sandbox                      changed: refuses after ensure_running when an agent is running
      │  ├─ Sandbox.is_agent_running()          new: `pgrep -x claude` in the sandbox
      │  └─ Sandbox.stop_hint()                 new
      ├─ Sandbox.attach(model) -> None          changed: runs `sbx run` and waits, no longer replaces the process
      │  └─ Host.run_in_terminal(command, env) -> int   new: SIGINT does nothing to foundry meanwhile
      └─ check_checkout_status(request, sandbox) -> CheckoutStatus    new
         ├─ Sandbox.is_running()                new: through list_live_sandboxes (unchanged)
         ├─ Sandbox.is_agent_running()          new (as above)
         └─ Sandbox.run(after_run_command)      unchanged

agent_runtime: check-unsaved-work               new command
└─ commands.check_unsaved_work.main -> int      new: prints the lines, or that both are saved
   └─ unsaved_work.unsaved_work(variables)    moved from claude_hooks; a failed fetch is "can't tell"; new wording

agent_runtime: claude-hook session-check        changed: also blocks when origin can't be reached (D1)
└─ unsaved_work.unsaved_work(variables)        (as above)
```

Removed: `Host.exec` and `SystemHost.exec`; in the tests, `FakeHost.exec`, `ExecCalled`, the two attach tests that use it, and `Attached`, which no test uses. `NoReturn` goes from `run.main`, `launch` and both `attach`.

## Steps
1. Runtime: move `unsaved_work` to `agent_runtime/unsaved_work.py`, with no behaviour change. Then the new wording and a failed fetch as "can't tell"; then `check-unsaved-work`.
2. `agent_sandbox`: `Host.run_in_terminal`, then `Sandbox.is_running`, `is_agent_running`, `stop_hint`. `attach` waits; `Host.exec` goes.
3. `agent_sandbox`: the refusal in `provision_sandbox` (AC5); `CheckoutStatus` and `check_checkout_status`; `launch` returns it; `LaunchRequest.after_run_command`.
4. foundry: `Session.launch_request` passes the command; `run.main` prints the report and returns its code.
5. The sbx tier: after provisioning, `check_checkout_status` on the real sandbox says both checkouts are saved.
6. Docs and the glossary's two terms.

## Names
| Change | Name | Signature | Its word comes from |
|---|---|---|---|
| added | runtime command `check-unsaved-work` | prints the lines on stdout; exits 0 when both are saved, 1 otherwise | the runtime's `check-hardening`, same shape; TASK.md "Terms": Unsaved work. Chosen by the human (LOG entry 9) |
| added | `agent_runtime.commands.check_unsaved_work.main`, `report` | `() -> int`; `(unsaved: list[str]) -> int` | `commands/check_hardening.py`'s `main` and `report` |
| moved | `agent_runtime.unsaved_work` module, and its `unsaved_work`, from `claude_hooks` | `(variables: SessionVariables) -> list[str]`, as today: one line per checkout not saved; empty when both are | TASK.md "Terms": Unsaved work; the function's name today |
| added | `LaunchRequest.after_run_command` | `tuple[str, ...]`, required | `init_command`, its neighbour |
| added | `agent_sandbox.CheckoutStatus` | frozen: `text: str`, `exit_code: int` (0 or 1); of both checkouts; exported from `agent_sandbox` | the term "Checkout status", which replaces TASK.md's "Exit report" (D2); `git status` |
| changed | `agent_sandbox.launch` | `(request: LaunchRequest) -> CheckoutStatus`, was `-> NoReturn` | the code |
| added | `launcher.check_checkout_status` | `(request: LaunchRequest, sandbox: Sandbox) -> CheckoutStatus` | as above; a verb, since it acts on the sandbox, as `provision_sandbox` does |
| changed | `Sandbox.attach` | `(model: str \| None) -> None`, was `NoReturn` | the code |
| added | `Sandbox.is_running` | `() -> bool`: `list_live_sandboxes` has it | `list_live_sandboxes`' "live"; sbx's status "running" |
| added | `Sandbox.is_agent_running` | `() -> bool` | Glossary: Agent run |
| added | `Sandbox.stop_hint` | `() -> str`: ``stop it with `sbx stop <name>` `` | `session.recreate_hint`; sbx's `stop` |
| added | `Host.run_in_terminal` | `(command: Sequence[str], env: Mapping[str, str]) -> int`, the exit code | new: on this process's terminal. Not "attach", which in `agent_sandbox` means attaching the agent |
| removed | `Host.exec` | | |
| changed | `commands.run.main` | `-> int`, was `NoReturn` | the code |

## Errors
The checkout status, on stderr, unprefixed, from `check-unsaved-work`:
- Both saved (AC1), exit 0: `both checkouts are saved on origin`
- One line for each checkout that isn't saved (AC2–AC3), exit 1:
  - `code checkout /home/agent/work/<repo> on task/wcf-0035: uncommitted changes`
  - `… : commits not pushed`
  - `… : uncommitted changes and commits not pushed`
  - `notes checkout /home/agent/work/<repo>-notes on agent-notes: can't tell: <reason>`
- A checkout's reasons:
  - `origin can't be reached: <git's first line>`: the fetch failed.
  - ``can't read it: `git -C <dir> status --porcelain` failed: <git's first line>``, or any other git command, or `can't read it: git not found in PATH`.

From `check_checkout_status`, when it can't run the command (AC3), exit 1:
- `can't tell: sandbox <name> is not running`
- ``can't tell: an agent is still running in sandbox <name>; stop it with `sbx stop <name>` ``
- `can't tell: <a SandboxError's text>`, such as `can't tell: sbx ls failed: <stderr>`.

The stop check's reason: `Cannot stop yet: <the lines, joined by "; ">. Commit and push that work (see "Git rules" in AGENTS.md), then finish.` Only the lines' wording changes.

The refusal (AC5), printed by `cli.py` as `error: …`, exit 1: ``an agent is already running in sandbox <name>, so no second one is started; stop it with `sbx stop <name>` ``

`Sandbox.is_agent_running` raises `SandboxError`: `could not check for a running agent: <stderr>`, when `pgrep` exits other than 0 or 1.

## Tests
- AC1–AC3, the lines: `tests/agent_runtime/test_unsaved_work.py`, its stop-check cases moved from `test_claude_hooks.py`, on the real checkouts of the `checkouts` fixture in `tests/agent_runtime/conftest.py`, through `check_unsaved_work.report` and `session_check`:
  - Both saved: the one line, exit 0.
  - Each of uncommitted, unpushed and both, in either checkout: the line naming it, its dir and branch, exit 1. A saved checkout gets no line.
  - Origin's URL pointed at a missing dir, after a commit that was pushed: the report says origin can't be reached, exit 1, and the stop check blocks with that reason (D1).
  - A removed checkout, and git missing: "can't read it".
  - The existing stop-check tests keep their cases; their expected text changes to the new wording.
- AC3, the sandbox: `tests/agent_sandbox/test_launcher.py`, against `FakeSandbox`, which gains `running` and `agent_running`, and records the attach:
  - A stopped sandbox: "can't tell", exit 1, and nothing runs in it, which would start it.
  - A running agent: "can't tell", with the stop hint.
  - A `SandboxError` from a check: "can't tell" with its text.
  - The command's exit 0 and its output: exit 0 and that text. Its exit 1: exit 1 and its stdout and stderr.
- `tests/agent_sandbox/test_sandbox.py`, against `FakeHost`:
  - `is_running` for "running", "stopped" and a sandbox not listed.
  - `is_agent_running` for pgrep's 0 and 1, and `SandboxError` for 2.
  - `stop_hint` names `sbx stop` and the sandbox.
- AC4:
  - `tests/agent_sandbox/test_host.py`, with a real child:
    - A child that sends SIGINT to foundry's process group, then exits, returns its code, and the test process lives.
    - A child that kills itself with SIGKILL returns -9, with no exception.
    - The old SIGINT handler is back afterwards.
  - By hand against real sbx: `kill` the `sbx run` from another terminal, then read the report.
- AC5: `test_launcher.py`: a running agent makes `provision_sandbox` raise the refusal, naming the sandbox and the stop hint, before GitHub access, the token or the init command. By hand: a second `foundry run` beside a running one.
- AC6:
  - `test_host.py`: the child starts with SIGINT at its default, read from `/proc/self/status`'s `SigIgn` and `SigCgt`.
  - `test_sandbox.py`: `attach` runs `sbx run` through `run_in_terminal`, with the sandbox's socket. This replaces the two `ExecCalled` tests.
  - By hand: one Ctrl-C clears the input and the run goes on; resizing works.
  - The sbx tier stops before attaching, as TASK.md's "Risks" says.
- AC7: read in review. `tests/test_docs.py` checks the links and paths.
- `tests/agent_kit/test_stop_hook.py`: the built runtime's `check-unsaved-work` against session-setup's checkouts, saved then not. This catches the command missing from the built runtime.
- `tests/test_run.py`: `launch_request` carries the kit's `check-unsaved-work` runtime command.
- `tests/sbx/test_smoke.py`: after provisioning, `check_checkout_status` on the real sandbox says both are saved, exit 0. This catches a template image without `pgrep`, a status other than "running", or the runtime unable to fetch over SSH.

## Docs
- `README.md`, "Use": what `foundry run` reports after the agent run, and its exit codes 0 and 1 (AC7).
- `ARCHITECTURE.md`:
  - Launch step 4: foundry runs `sbx run` and waits, then runs `check-unsaved-work` and prints the checkout status. Cut "foundry never learns how the agent run ended" (AC7).
  - The runtime's commands table: `check-unsaved-work`, run by foundry after each agent run.
- `GLOSSARY.md`: "Unsaved work" and "Checkout status", from TASK.md's "Terms" (D2), with the `domain-modeling` skill.
- Docstrings:
  - `launcher.py`'s module docstring and `launch`.
  - `Sandbox.attach` and `SbxCli.attach`.
  - `cli.main`, which says commands may replace the process.
  - `claude_hooks.py`'s module docstring: `session-check`'s rule is now `unsaved_work`'s.
- `ARCHITECTURE.md`'s runtime codemap: `unsaved_work.py`.
- `CONTRIBUTING.md`'s sbx section still holds: the tier stops before attaching.
