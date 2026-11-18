# Plan: wcf-0036

Built on wcf-0035 as approved, at 5460996 on `task/wcf-0035` (PR #87, not merged yet). TASK.md's "wcf-0035's exit report" is its **checkout status**: wcf-0035 renamed the term (its D2), and GLOSSARY.md lists "exit report" under _Avoid_.

## Approach
A headless run replaces only the attach. Provisioning, its refusal beside a running agent (AC10) and the checkout status are wcf-0035's, unchanged. Then, instead of `sbx run`, foundry starts the agent with `sbx env exec <definition dir> -- sh -c 'cd "$1" && shift && exec "$@"' sh <workspace> claude --dangerously-skip-permissions -p --output-format stream-json --verbose [--model M] "<opening prompt>"`. Probe L4 (wcf-0035 LOG entry 4) showed this streams pure JSON, one event per line, as the agent works. `sbx run` piped prints nothing (L1), and under a pty mixes in sbx's own lines and escapes (L2). `--dangerously-skip-permissions` and the workspace as working dir are what `sbx run` gives the interactive agent (probe O3's `ps`). `sbx env exec` runs as the agent user, as `session-init` does.

foundry reads the event lines as they come and turns each into live-view lines, logged as progress (DR6), so they show on stderr as `==>` lines (AC6). One new module, `agent_sandbox/agent_events.py`, knows Claude Code's stream-json format: a format change is one edit there (TASK.md "Risks"). From each event it takes:
- `assistant` events: one line per `tool_use` block, `<tool name>: <main argument>`, and one per non-empty `text` block, `agent: <its first non-blank line>`. The main argument is the input's first string field among `command`, `file_path`, `notebook_path`, `pattern`, `url`, `query`, `skill`, `description`, `prompt`; with none, the tool's name alone. Whitespace runs, newlines included, become one space, and a line longer than the width is cut, ending in `…`. `thinking` blocks, `user` events (tool results), `system` events and any other type give nothing (AC6).
- the `result` event: with `is_error` false, its `result` is the final message (AC7). With `is_error` true, the run failed, with `result` as the reason, or its `subtype` when `result` is empty (AC8).
- a line that isn't a JSON object gives nothing for the live view and shows only with `-v`. L4 saw none; this keeps an unexpected sbx warning from ending a run the agent is still doing.

The child `sbx env exec` runs in its own process group, with stdin empty and stderr passed through to foundry's. A Ctrl-C then reaches only foundry, as a `KeyboardInterrupt` while it reads (AC9). foundry then, with SIGINT doing nothing to it (so a second Ctrl-C can't cut the report short):
1. ends the `sbx env exec` child, which may or may not take the agent with it (L5);
2. stops the agent in the sandbox: `timeout 10 sh -c 'pkill -TERM -x claude; while pgrep -x claude >/dev/null; do sleep 0.5; done'` (probe O3 stopped one in under 5 s). Its exit code is not read;
3. takes the checkout status, which says "can't tell" when the agent is still running (wcf-0035's check);
4. kills any agent left: `pkill -KILL -x claude`, so none is left running (AC9).

The names match exactly, never `sleep` or a bare pattern (wcf-0035 LEARNINGS, 2026-11-17).

`launch` returns an `AgentRunResult`: the checkout status, and for a headless run the final message or why it failed. `run.main` prints the final message on stdout, then `error: <failure>` and the checkout status on stderr, and exits with `AgentRunResult.exit_code`: 1 when the run failed, else the status's code (AC7, AC8). An interrupted run has no failure, so it exits with the status's code (AC9). Printing and the exit code are the only branches in `main` (DR7). Choosing headless or interactive happens in `run_agent` and `choose_headless`, which the tests call.

`headless` sits in each role's options beside `model` and, like it, is read at each launch, not stored in the sandbox (ADR-0014, ADR-0004). `config.parse` refuses a role without it, so `foundry run` stops at `config.load`, its first step, before any clone or sandbox (AC1).

Turned down:
- **`sbx run -- -p …` under a pseudo-terminal, filtering out sbx's lines and escapes (L2).** More code to keep in step with sbx's output, which is not an interface. It breaks nothing in TASK.md; it loses on cost alone, which the human weighed in wcf-0035's LOG entry 5 when choosing `sbx env exec`.
- **Text-mode `-p` (L3).** Nothing shows until the end, breaking AC6.
- **Killing only the `sbx env exec` child on Ctrl-C.** L5 couldn't show it stops the agent, so AC9's "no agent left running" would rest on luck.
- **A `default: false` for `Role.headless`, or a missing key read as interactive.** Breaks AC1.
- **Printing the live view from `run.main`, through a callback.** The lines are progress, and only entry points print (DR6); the logger already carries progress to stderr.

Open, judgement calls; neither option of each breaks a criterion, out-of-scope line, rule or ADR:
- **J1, the live view's width.**
  - A (recommended): a fixed 76 characters, so a line and its `==> ` fit an 80-column terminal. Cost: wide terminals see commands cut sooner.
  - B: the terminal's width, read from stderr, minus 4. Cost: a new `Host` method, and the launcher knowing the progress prefix's length, which `cli.py` owns.
- **J2, YAML's other spellings of a boolean.** `config/foundry.yaml` is read with `yaml.safe_load`, which reads `yes`, `on` and `True` as true.
  - A (recommended): accept whatever YAML reads as a boolean. Cost: `headless: yes` is not refused, though AC1 names only `true` and `false`.
  - B: refuse anything but `true` and `false` as written. Cost: a YAML loader of foundry's own in `yaml_io.py`, for one key.

## Shape

```
foundry.commands.run
├─ add_parser                                       changed: --interactive and --headless, mutually exclusive
└─ main -> int                                      changed: prints the final message, a failure, then the checkout status
   ├─ config.load                                   changed: each role must say headless: true or false
   ├─ choose_headless(role, override) -> bool       new
   ├─ Session.launch_request(*, headless)           changed: carries headless
   └─ agent_sandbox.launch(request) -> AgentRunResult       changed: was -> CheckoutStatus
      ├─ provision_sandbox                          unchanged: refuses beside a running agent (AC10)
      ├─ launch_summary                             changed: a `run:` line, headless or interactive
      └─ run_agent(request, sandbox) -> AgentRunResult      new
         ├─ Sandbox.attach(model)                   unchanged, when not headless
         ├─ Sandbox.run_headless(model) -> Generator[str]   new: the agent's event lines
         │  └─ Host.run_streaming(command, env)     new
         ├─ agent_events.read_agent_event(line) -> AgentEvent   new
         ├─ host.outliving_interrupts()             new: context manager; run_in_terminal uses it too
         ├─ Sandbox.stop_agent()                    new, after an interrupt
         ├─ check_checkout_status(request, sandbox) unchanged
         └─ Sandbox.kill_agent()                    new, after an interrupt
```

`SbxCli.__init__` gains `workspace_dir`, from the definition, for the headless agent's working dir.

## Steps
1. Config: `headless` required, `Role.headless`, the shipped config, and every test config and `Role(...)` given it (AC1, AC2).
2. `host.py`: `outliving_interrupts`, then `run_in_terminal` on it, with no behaviour change. Then `run_streaming`.
3. `sandbox.py`: `workspace_dir`, `run_headless`, `stop_agent`, `kill_agent`.
4. `agent_events.py`: `read_agent_event` and `AgentEvent`.
5. `launcher.py`: `AgentRunResult`, `run_agent`, `LaunchRequest.headless`, the summary line; `launch` returns `AgentRunResult`.
6. `run.py` and `session.py`: the two flags, `choose_headless`, `launch_request(headless=…)`, the printing.
7. The sbx tier: `stop_agent` and `kill_agent` on the real sandbox, with no agent running.
8. Docs and the glossary's three terms.

## Names
| Change | Name | Signature | Its word comes from |
|---|---|---|---|
| added | role option `headless` | `true` or `false`, required | TASK.md AC1, "Terms": Headless run |
| added | `Role.headless` | `bool`, required, after `github_token_path` | the option |
| added | `foundry run --headless`, `--interactive` | flags, one `dest`: `headless`, `True`, `False` or `None` | TASK.md AC3 |
| added | `commands.run.choose_headless` | `(role: Role, override: bool \| None) -> bool`: `override`, or the role's when None | `choose_role`, beside it |
| changed | `Session.launch_request` | `(*, headless: bool) -> LaunchRequest`, was `()` | the code |
| added | `LaunchRequest.headless` | `bool = False` | the option. Defaulted like `model`, as the launcher is given it, not configured |
| added | `agent_sandbox.AgentRunResult` | frozen: `checkout_status: CheckoutStatus`, `final_message: str \| None = None`, `failure: str \| None = None`; property `exit_code -> int`; exported | Glossary: Agent run; stream-json's own `result` event, which it carries |
| changed | `agent_sandbox.launch` | `(request) -> AgentRunResult`, was `-> CheckoutStatus` | the code |
| added | `launcher.run_agent` | `(request: LaunchRequest, sandbox: Sandbox) -> AgentRunResult` | Glossary: Agent run; a verb, as `provision_sandbox` |
| added | `Sandbox.run_headless`, `SbxCli.run_headless` | `(model: str \| None) -> Generator[str, None, None]`: the agent's event lines; closing it ends the `sbx env exec` | Glossary: Headless run; `attach`, its interactive twin |
| added | `Sandbox.stop_agent` | `() -> None`: SIGTERM, then waits up to 10 s | `stop_hint`; Glossary: Agent run |
| added | `Sandbox.kill_agent` | `() -> None`: SIGKILL to any agent left | `kill`, the signal it sends |
| added | `SbxCli(…, workspace_dir: Path)` | keyword | `SandboxDefinition.workspace_dir` |
| added | `Host.run_streaming` | `(command: Sequence[str], env: Mapping[str, str]) -> Generator[str, None, None]`: each stdout line as it is written; own process group; stdin empty; stderr passed through | `run`, `run_in_terminal`, its neighbours |
| added | `host.outliving_interrupts` | `() -> ContextManager[None]`: SIGINT does nothing to this process inside | `_outlive_interrupt_handler`, which it installs |
| added | module `agent_sandbox/agent_events.py` | | Claude Code's word "events" for stream-json lines. The one module that knows that format |
| added | `agent_events.AgentEvent` | frozen: `live_view: tuple[str, ...]`, `final_message: str \| None`, `failure: str \| None` | as above; TASK.md "Terms": Live view |
| added | `agent_events.read_agent_event` | `(line: str) -> AgentEvent` | `SandboxDefinition.read` |
| added, private | `sandbox._AGENT_STOP_WAIT_SECONDS` | `10` | TASK.md AC9 |
| added, private | `agent_events._LIVE_VIEW_WIDTH` | `76` (J1, option A) | TASK.md "Terms": Live view |

## Errors
- AC1, from `config.parse`, printed by `cli.py` as `error: …`, exit 1:
  - missing: `config/foundry.yaml: roles.dev has no headless: say headless: true or headless: false`
  - another value: `config/foundry.yaml: roles.dev.headless is 'sometimes': say headless: true or headless: false`
  - changed, an unknown option: `config/foundry.yaml: roles.dev: unknown role option 'x'; the options are 'headless' and 'model'`
  - changed, not a mapping: `config/foundry.yaml: roles.dev must be a mapping, such as {headless: true} or {headless: false, model: opus}`
- AC3, argparse's own, exit 2: `foundry run: error: argument --interactive: not allowed with argument --headless` (whichever came second).
- AC8, on stderr, before the checkout status, exit 1:
  - `error: the agent run failed: <result's text, or its subtype>`
  - `error: the agent's process ended without a final message`
- Progress, on stderr:
  - the live view: `==> Bash: uv run pytest -q`, `==> Read: /home/agent/work/willcode-foundry/README.md`, `==> agent: Merged origin/HEAD; running the checks now.`
  - on Ctrl-C: `==> interrupted: stopping the agent`
  - the launch summary's new line: `==> run:        headless` or `==> run:        interactive`
- `SbxCli.run_headless` raises `SandboxError("sbx not found in PATH")` through `run_streaming`, as `run` does.

## Tests
- AC1: `tests/test_config.py`, through `config.parse`: a role with no options, with options lacking `headless`, and with `headless: "sometimes"` and `headless: 1` are each refused with the message above; `true` and `false` read as given. `tests/test_run.py`: `cli.main(["run", …])` on a config whose role lacks it returns 1 with the error, and no `sessions/` dir exists after.
- AC2: `tests/test_config.py`: this foundry's own `config/foundry.yaml` makes dev, reviewer and qa headless, planner and architect not.
- AC3: `tests/test_run.py`: `build_parser()` parses each flag to `headless` `True` and `False`, and neither to `None`; both raise `SystemExit(2)`; `--help` names both. `choose_headless`: each override wins over the role's either way; `None` gives the role's.
- AC4: wcf-0035's tests stay as they are, but for the return type. `test_launcher.py`: `run_agent` on a request that isn't headless attaches with the model and returns the checkout status, with no final message and no failure, and runs nothing headless.
- AC5: `test_launcher.py`, against `FakeSandbox`, which gains `event_lines` to yield, a recorded `headless_models`, and `stop_agent`/`kill_agent` counts: a headless request runs headless with the model, never attaches, and returns once the lines end. `test_sandbox.py`, against `FakeHost` (gains `streamed` responses): `run_headless` streams `sbx env exec <definition dir> -- sh -c … <workspace> claude --dangerously-skip-permissions -p --output-format stream-json --verbose --model m "<opening prompt>"` with the sandbox's socket, and leaves out `--model` for None. By hand against real sbx: a headless dev run on a throwaway task commits, pushes and returns by itself; the stop check blocks a stop with unsaved work.
- AC6: `tests/agent_sandbox/test_agent_events.py`, on JSON lines shaped like L4's: a `tool_use` per main-argument key; a tool with none; a multi-line command on one line; a long one cut to 76 with `…`; a text block's first non-blank line; two blocks in one event, two lines; `thinking`, `user`, `system` and an unknown type give nothing; a non-JSON line gives nothing. `test_launcher.py`: `run_agent` logs each live-view line at INFO as it reads it (caplog), and nothing of a tool result. `test_host.py`: `run_streaming` yields a real child's first line before the child ends (the child waits for a file the test writes after reading it). By hand: lines appear as the agent works.
- AC7: `test_agent_events.py`: a success `result` gives its final message. `test_launcher.py`: the result carries it and the checkout status, `exit_code` is the status's. `test_run.py` can't reach `run.main`'s prints without a sandbox; they are held by review (DR7). By hand: the final message on stdout (`foundry run … >out`), the status on stderr after it.
- AC8: `test_agent_events.py`: an `is_error` result gives its `result` as the failure, or its subtype when empty. `test_launcher.py`: a failed result, and lines that end with no result, each give that failure and `exit_code` 1 with a saved checkout status. By hand: a role whose model is `claude-no-such-model` prints Claude Code's error, the status, and exits 1.
- AC9: `test_launcher.py`, with the real `outliving_interrupts`:
  - a `FakeSandbox` whose lines raise `KeyboardInterrupt` midway: `run_agent` stops the agent, takes the status, then kills any left, in that order; no failure; `exit_code` is the status's; the headless generator was closed.
  - its `stop_agent` sends this process SIGINT (a second Ctrl-C): the result still returns.
  - an agent that outlives `stop_agent`: the status says "can't tell" with the agent still running, and `kill_agent` runs after.
  - `test_sandbox.py`: `stop_agent` and `kill_agent` run their exact commands, by exact name, through `sbx env exec`.
  - `test_host.py`: `outliving_interrupts` lets this process survive SIGINT inside and puts the old handler back; `run_streaming`'s child is in another process group; closing it early terminates the child.
  - By hand: Ctrl-C midway, a second Ctrl-C while it waits, then `sbx env exec … ps` shows no `claude`.
- AC10: the refusal is in `provision_sandbox`, which `launch` runs before `run_agent` whatever the request (DR7, by review). `test_launcher.py`: wcf-0035's refusal test, parametrized over a headless and an interactive request. By hand: a headless launch beside a running agent is refused.
- AC11: read in review; `tests/test_docs.py` checks links and paths.
- `tests/sbx/test_smoke.py`: `stop_agent`, then `kill_agent`, on the real sandbox with no agent, return, and the sandbox is still running. This catches `timeout`, `pkill` or `pgrep` missing from the template image.
- `test_host.py`: `outliving_interrupts` is what `run_in_terminal` uses: the existing three interrupt tests pass unchanged after step 2's refactor.

## Docs
- `README.md`, "Use" (AC11): making a role headless in `config/foundry.yaml`; `--headless` and `--interactive`; what a headless run prints (live view on stderr, final message on stdout, then the checkout status), its exit codes; stopping one with Ctrl-C.
- `config/foundry.yaml`'s comment on roles: `headless` beside `model`.
- `ARCHITECTURE.md`: launch step 4 gains the headless path; the codemap's `agent_sandbox/` row names `agent_events.py`.
- `GLOSSARY.md`: Headless run, Interactive run and Live view, from TASK.md's "Terms", with the `domain-modeling` skill.
- `CONTRIBUTING.md`'s sbx section: the tier still stops before an agent runs; headless runs are checked by hand.
- Docstrings: `launcher.py`'s module docstring and `launch`; `run.py`'s module docstring and `main`; `Role`; `LaunchRequest`; `Session.launch_request`.
