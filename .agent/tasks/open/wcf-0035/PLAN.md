# Plan: wcf-0035

## Approach
`foundry run` stops replacing itself with `sbx run`. It runs `sbx run` as a child on the same terminal, waits for it, then checks the sandbox and prints the exit report. The check has three parts, in order:

1. Is the sandbox running? Asked with `sbx ls --json`, which never starts it. Not running: can't tell (AC3).
2. Is an agent still running in it? Asked with `pgrep -x claude` through `sbx env exec`. Yes: can't tell (AC3).
3. The runtime's new `unsaved-work` command, run in the sandbox like `session-init`, prints each checkout's unsaved work as JSON. foundry reads it and prints the report (AC1–AC3).

Step 2's check also runs before attaching, right after the sandbox is started, and refuses the launch when an agent is running (AC5). Its message gives a stop command, `sbx stop <name>`, which stops the whole sandbox; the next launch starts it again. The human chose it over killing the agent's process (LOG entry 8).

The stop check and `unsaved-work` share one definition of unsaved work, in a new runtime module (TASK.md "Terms"). They differ in one way, named by an enum: when `git fetch` fails, the stop check compares with the last fetched state, as today (OS1). The report says "can't tell" (AC3).

While it waits, foundry swaps SIGINT's handler for one that does nothing, and puts the old one back after. A Ctrl-C that reaches foundry's process group, outside sbx's raw mode, then can't kill foundry before the report (AC4). The child starts with the default handler, since exec resets caught signals, so sbx and Claude Code see Ctrl-C as today (AC6). The child shares the terminal and process group, so it gets SIGWINCH as today (AC6).

Turned down:
- **foundry running the git commands itself through `sbx env exec`**, one call each. It gives the report a second definition of unsaved work, which TASK.md's "Terms" says the stop check and the report share.
- **The JSON's format in the new runtime module, imported by foundry.** foundry would import a fifth runtime module. Because: DR2. The format goes in `agent_runtime/contract.py` instead, already shared, and spelled once there. Because: DR1.
- **Reporting a failed `sbx ls` or `pgrep` after the run as an error.** AC3 asks for "can't tell" with the reason, so `check_after_run` turns `SandboxError` into one.
- **Reusing `claude-hook session-check` after the run.** It speaks Claude Code's hook protocol: it reads a Stop event on stdin and prints a block decision as prose, without each checkout's dir and branch (AC2). Offline, it compares with the last fetch, which OS1 keeps and AC3 forbids for the report.
- **`pkill -TERM -x claude` as the stop command.** It needs the sandbox's socket in front of it, and it matches the agent by process name. The human chose `sbx stop` (LOG entry 8).
- **`SIG_IGN` while waiting.** The child inherits an ignored signal across exec, so Ctrl-C would stop reaching sbx. Breaks AC6.
- **Telling a running agent apart by `sbx ls`.** It lists sandboxes, not agents: a sandbox stays running after its agent run ends (probe U1, LOG entry 2).

Accepted: a sandbox that stops between `sbx ls` and the `env exec` after it would be started again by that call. The window is a fraction of a second.

## Shape

```
foundry.cli.main                                    changed: docstring; no command replaces the process any more
└─ commands.run.main                                changed: returns the exit report's exit code, prints its lines on stderr
   ├─ Session.launch_request                        changed: adds after_run_command, the runtime's `unsaved-work`
   ├─ agent_sandbox.launch(request) -> AfterRunCheck   changed: waits for the agent run, then checks
   │  ├─ provision_sandbox                          changed: refuses after ensure_running when an agent is running
   │  │  ├─ Sandbox.agent_running()                 new: `pgrep -x claude` in the sandbox
   │  │  └─ Sandbox.stop_command()                  new: the command a person runs to stop it
   │  └─ attach_and_check(request, sandbox)         new: attach, then check_after_run, whatever the attach returned
   │     ├─ Sandbox.attach(model) -> None           changed: runs `sbx run` and waits, no longer replaces the process
   │     │  └─ Host.run_attached(command, env) -> int   new: on this terminal; SIGINT does nothing to foundry meanwhile
   │     └─ check_after_run(request, sandbox)       new
   │        ├─ Sandbox.is_running()                 new: `sbx ls --json`; never starts the sandbox
   │        ├─ Sandbox.agent_running()              new (as above)
   │        └─ Sandbox.run(after_run_command)       unchanged
   └─ exit_report.exit_report(check) -> ExitReport  new: reads the JSON through contract, and words the report

agent_runtime: unsaved-work                         new command
└─ commands.unsaved_work.main                       new: reads the session variables, prints the JSON
   └─ unsaved_work.unsaved_work(variables, WhenOffline.CANT_TELL)   new: the shared definition
      └─ contract.unsaved_work_json(...)            new

agent_runtime: claude-hook session-check            unchanged behaviour (OS1)
└─ claude_hooks.unsaved_work(variables)             changed: words unsaved_work.unsaved_work(variables,
                                                    WhenOffline.COMPARE_WITH_LAST_FETCH); same messages as today
```

`Host.exec` goes, since nothing calls it any more.

## Steps
1. Refactor, with no behaviour change: move the stop check's git logic from `claude_hooks.py` into `agent_runtime/unsaved_work.py`. Add `CheckoutUnsavedWork` to `contract.py`. `claude_hooks.unsaved_work` keeps its messages, so `test_claude_hooks.py` and `test_stop_hook.py` pass unchanged.
2. Add `WhenOffline.CANT_TELL`, the `unsaved-work` runtime command and its JSON, with `read_unsaved_work_json` in `contract.py`.
3. `agent_sandbox`: `Host.run_attached`, then `Sandbox.is_running`, `agent_running`, `stop_command`. `attach` waits; `Host.exec` goes.
4. `agent_sandbox`: the refusal in `provision_sandbox` (AC5); `attach_and_check` and `check_after_run`; `launch` returns `AfterRunCheck`; `LaunchRequest.after_run_command`.
5. foundry: `exit_report.py`, `Session.launch_request` passing the command, and `run.main` printing the report and returning its code.
6. The sbx tier: after provisioning, `check_after_run` on the real sandbox reports both checkouts saved.
7. Docs and the glossary's two terms.

## Names
| Change | Name | Signature | Its word comes from |
|---|---|---|---|
| added | `agent_runtime.unsaved_work` module | | TASK.md "Terms": Unsaved work |
| added | `unsaved_work.unsaved_work` | `(variables: SessionVariables, when_offline: WhenOffline) -> tuple[CheckoutUnsavedWork, CheckoutUnsavedWork]`, code checkout first | as above |
| added | `unsaved_work.WhenOffline` | enum: `COMPARE_WITH_LAST_FETCH`, `CANT_TELL` | new: what a failed fetch makes it do |
| added | `contract.CheckoutUnsavedWork` | frozen, kw_only: `checkout: str` ("code checkout" or "notes checkout"), `checkout_dir: Path`, `branch: str`, `uncommitted: bool`, `unpushed: bool`, `cant_tell: str \| None` (why; both bools are then False); property `saved: bool` | "Code checkout", the session variables' `*_checkout_dir`, AC2–AC3's "can't tell" |
| added | `contract.unsaved_work_json`, `contract.read_unsaved_work_json` | `(works: Sequence[CheckoutUnsavedWork]) -> str`; `(text: str) -> tuple[CheckoutUnsavedWork, ...]`; round-trips | as above |
| added | runtime command `unsaved-work` | prints the JSON on stdout, exits 0 | as above |
| added | `agent_runtime.commands.unsaved_work.main` | `() -> None` | as above |
| changed | `claude_hooks.unsaved_work` | unchanged signature and messages | the code |
| added | `LaunchRequest.after_run_command` | `tuple[str, ...]`, required | `init_command`, its neighbour |
| added | `agent_sandbox.AfterRunCheck`, `Checked`, `Unchecked` | `Checked(output: str)` (what the command printed), `Unchecked(reason: str)`; `AfterRunCheck = Checked \| Unchecked`; exported from `agent_sandbox` | new: agent_sandbox doesn't know what the command checks |
| changed | `agent_sandbox.launch` | `(request: LaunchRequest) -> AfterRunCheck`, was `-> NoReturn` | the code |
| added | `launcher.attach_and_check`, `launcher.check_after_run` | `(request: LaunchRequest, sandbox: Sandbox) -> AfterRunCheck` each | the code's `attach` |
| changed | `Sandbox.attach` | `(model: str \| None) -> None`, was `NoReturn` | the code |
| added | `Sandbox.is_running` | `() -> bool`: `sbx ls --json` lists it as `"running"` | sbx's status |
| added | `Sandbox.agent_running` | `() -> bool` | Glossary: Agent run |
| added | `Sandbox.stop_command` | `() -> str`, shell-quoted | sbx's `stop` |
| added | `Host.run_attached` | `(command: Sequence[str], env: Mapping[str, str]) -> int`, the exit code | the code's `run` |
| removed | `Host.exec` | | |
| added | `foundry.exit_report` module, `exit_report` | `(check: AfterRunCheck) -> ExitReport` | TASK.md "Terms": Exit report |
| added | `exit_report.ExitReport` | frozen: `lines: tuple[str, ...]`, `exit_code: int` | as above |
| changed | `commands.run.main` | `-> int`, was `NoReturn` | the code |

## Errors
The exit report, each line on stderr, unprefixed:
- Both saved (AC1), exit 0: `both checkouts are saved on origin`
- One line for each checkout that isn't saved (AC2–AC3), exit 1:
  - `code checkout /home/agent/work/<repo> on task/wcf-0035: uncommitted changes`
  - `… : commits not pushed`
  - `… : uncommitted changes and commits not pushed`
  - `notes checkout /home/agent/work/<repo>-notes on agent-notes: can't tell: <reason>`
- A checkout's reasons, from the runtime:
  - `origin can't be reached: <git's first line>`: the fetch failed.
  - ``can't read it: `git -C <dir> status --porcelain` failed: <git's first line>``, or any other git command, or `can't read it: git not found in PATH`.
- The sandbox couldn't be checked (AC3), exit 1: `can't tell whether work is unsaved: <reason>`, where the reason is one of:
  - `sandbox <name> is not running`
  - `an agent is still running in sandbox <name>; stop it with: <stop command>`
  - `` `<after-run command>` failed in sandbox <name>: <its stderr> ``
  - a `SandboxError`'s text, such as `sbx ls failed: <stderr>`.
- The refusal (AC5), printed by `cli.py` as `error: …`, exit 1: `an agent is already running in sandbox <name>, so no second one is started; stop it with: <stop command>`
- The stop command: `sbx stop <name>`
- `Sandbox.agent_running` raises `SandboxError`: `could not check for a running agent: <stderr>`, when `pgrep` exits other than 0 or 1.
- The stop check's messages don't change (OS1).

## Tests
- AC1: `tests/test_exit_report.py`: two saved checkouts give the one line and exit 0. The JSON comes from `contract.unsaved_work_json`, never written by hand.
- AC2: same file: each of uncommitted, unpushed, both, in either checkout, gives the line naming the checkout, its dir and branch, and exit 1. Saved checkouts get no line.
- AC3:
  - `tests/test_exit_report.py`: `Unchecked` and a checkout's `cant_tell` each give "can't tell" with the reason, and exit 1.
  - `tests/agent_runtime/test_unsaved_work.py`, on the real checkouts of the `checkouts` fixture in `tests/agent_runtime/conftest.py`:
    - With origin's URL pointed at a missing dir, after a commit that was pushed: `CANT_TELL` says origin can't be reached. `COMPARE_WITH_LAST_FETCH` says saved, which shows OS1's offline behaviour is kept.
    - A removed checkout can't be read.
    - Uncommitted and unpushed are each reported.
  - `tests/agent_sandbox/test_launcher.py`, against `FakeSandbox` (gaining `running`, `agent_running` and a recorded attach):
    - A stopped sandbox gives `Unchecked`, and nothing runs in it, which would start it.
    - A running agent gives `Unchecked`, with the stop command.
    - The command failing gives `Unchecked`.
    - A `SandboxError` from a check gives `Unchecked` with its text.
    - Otherwise `Checked` with its output.
  - `tests/agent_sandbox/test_sandbox.py` against `FakeHost`:
    - `is_running` for "running", "stopped" and a sandbox not listed.
    - `agent_running` for pgrep's 0 and 1, and `SandboxError` for 2.
  - `tests/agent_runtime/test_contract.py`: the JSON round-trips.
- AC4:
  - `test_launcher.py`: `attach_and_check` checks after any attach.
  - `tests/agent_sandbox/test_host.py`, with a real child:
    - A child that sends SIGINT to foundry's process group, then exits, returns its code, and the test process lives.
    - A child that kills itself with SIGKILL returns -9, with no exception.
    - The old SIGINT handler is back afterwards.
  - By hand against real sbx: `kill` the `sbx run` from another terminal, then read the report.
- AC5: `test_launcher.py`: a running agent makes `provision_sandbox` raise the refusal, naming the sandbox and the stop command, before GitHub access, the token or the init command. `test_sandbox.py`: the stop command is `sbx stop` with the sandbox's name. By hand: a second `foundry run` beside a running one.
- AC6:
  - `test_host.py`: the child starts with SIGINT at its default, read from `/proc/self/status`'s `SigIgn` and `SigCgt`.
  - `test_sandbox.py`: `attach` runs `sbx run` through `run_attached`, with the sandbox's socket. This replaces the two `ExecCalled` tests.
  - By hand: one Ctrl-C clears the input and the run goes on; resizing works.
  - The sbx tier stops before attaching, as TASK.md's "Risks" says.
- AC7: read in review. `tests/test_docs.py` checks the links and paths.
- `tests/agent_kit/`: the built runtime's `unsaved-work` prints JSON `contract` reads, against session-setup's checkouts. This catches the command missing from the built runtime.
- `tests/test_run.py`: `launch_request` carries the kit's `unsaved-work` runtime command.
- `tests/sbx/test_smoke.py`: after provisioning, `check_after_run` on the real sandbox gives `Checked`, and its JSON says both saved. This catches a template image without `pgrep`, a status other than "running", or the runtime unable to fetch over SSH.

## Docs
- `README.md`, "Use": what `foundry run` reports after the agent run, and its exit codes 0 and 1 (AC7).
- `ARCHITECTURE.md`:
  - Launch step 4: foundry runs `sbx run` and waits, then runs `unsaved-work` and prints the exit report. Cut "foundry never learns how the agent run ended" (AC7).
  - The runtime's commands table: `unsaved-work`, run by foundry after each agent run.
  - Codemap rows for `exit_report.py`, `unsaved_work.py`, and `contract.py`'s new contents.
- `GLOSSARY.md`: "Unsaved work" and "Exit report", from TASK.md's "Terms", with the `domain-modeling` skill.
- Docstrings:
  - `launcher.py`'s module docstring and `launch`.
  - `Sandbox.attach` and `SbxCli.attach`.
  - `Host`'s, for `exec` going.
  - `cli.main`, which says commands may replace the process.
  - `claude_hooks.py`'s module docstring.
  - `contract.py`'s one-line purpose.
- `CONTRIBUTING.md`'s sbx section still holds: the tier stops before attaching.
