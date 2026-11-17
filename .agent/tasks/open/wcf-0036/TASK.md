# Task wcf-0036: Run a role headless

<!-- Part of: agent runs that end by themselves and report their unsaved work
(slice 2 of 2; slice 1 is wcf-0035, whose LOG.md entries 2–5 hold the sbx facts and the agreed scope).
After: wcf-0035. -->

## Goal
Today every agent run holds a terminal until the human types `/exit`, even
for roles that need no conversation, so the human must sit with each run to
know it ended and what it left. A role should be able to run headless: the
agent run ends by itself when the agent stops, `foundry run` shows what it
is doing as it works, and then prints wcf-0035's exit report. Whether each
role runs headless is set in `config/foundry.yaml`, and can be overridden for
one launch.

## Acceptance criteria
- [ ] AC1: Each role in `config/foundry.yaml` must say `headless: true` or
      `headless: false`, beside its model. `foundry run` refuses a config
      where any role says neither, or gives another value, before any sandbox
      is touched: it exits 1 with an error naming the role, the value (if
      any), and the two allowed values.
- [ ] AC2: The shipped `config/foundry.yaml` makes dev, reviewer and qa
      headless, and planner and architect interactive.
- [ ] AC3: `foundry run --interactive` and `foundry run --headless` launch an
      interactive or a headless run whatever the config says; giving both is
      a usage error, exit 2, before anything runs. `foundry run --help` shows both.
- [ ] AC4: An interactive run behaves as wcf-0035 leaves it.
- [ ] AC5: A headless launch provisions and checks the sandbox as an
      interactive launch does, then starts the agent as the same user, on the
      opening prompt and the role's model, with no terminal UI, and
      `foundry run` returns by itself when the agent stops, without the human typing anything. The agent's
      stop check still applies before it stops.
- [ ] AC6: While a headless run works, `foundry run` prints on stderr, as
      each happens and not at the end: one line per tool call, giving the
      tool's name and its main argument (such as the command, file path or
      pattern), and one line per message from the agent, giving its first
      line. Each fits one terminal line. Tool results and raw JSON are never
      printed.
- [ ] AC7: When a headless run ends, the agent's final message is printed in
      full on stdout, then wcf-0035's exit report on stderr, and `foundry run`
      exits with the report's code.
- [ ] AC8: When Claude Code reports a failed run (such as an API or
      credentials error), or the agent's process ends without a final
      message, `foundry run` prints that error, then the exit report, and
      exits 1 whatever the report says.
- [ ] AC9: On Ctrl-C during a headless run, `foundry run` stops the agent in
      the sandbox, then prints the exit report and exits with its code. A
      second Ctrl-C while it waits doesn't cut the report short. If the agent
      hasn't stopped within 10 seconds, the report says "can't tell" because
      the agent is still running. Afterwards no agent is left running in the
      sandbox.
- [ ] AC10: A headless launch beside an agent already running in the sandbox
      is refused, as wcf-0035 refuses an interactive one.
- [ ] AC11: `README.md` says how to make a role headless, the two flags, what a
      headless run prints, and how to stop one. `GLOSSARY.md` holds the terms
      below.

## Out of scope
- OS1: A time limit on headless runs.
- OS2: Saving the live view, or the agent's raw events, to a file.
- OS3: Resuming a headless conversation: an agent records what it needs in
  the task notes, and a human answers through `LOG.md` and `foundry task
  handoff`, or by launching the role interactively.
- OS4: Starting the next role when a turn ends.
- OS5: What an agent does differently when headless: its instructions, hooks
  and stop check stay as they are.
- OS6: A report when `foundry run` itself is killed, as wcf-0035's OS6.

## Risks
- wcf-0035 is not planned yet; its exit report and its refusal beside a
  running agent are what AC7–AC10 build on, and its plan may shape them.
- The probes behind this design (wcf-0035 LOG entries 2–4, sbx v0.46.0) ran
  in throwaway sandboxes without foundry's kit or managed settings. Whether a
  headless run started this way gets the same environment, hooks and
  permissions as an interactive one in a real foundry sandbox is unproven.
- In probe L5, killing the process that ran the headless agent may or may
  not have stopped the agent; probe O3 showed stopping it inside the sandbox
  works.
- The sbx tier stops before attaching an agent, so AC5–AC9 may need checking
  by hand against real sbx.
- Requiring `headless` breaks every existing `config/foundry.yaml` and test
  config whose roles lack it, until it is added.
- The headless run's event stream is Claude Code's output format, which can
  change between Claude Code versions.
- No existing follow-up touches this code.

## Terms
- **Headless run**: an agent run with no terminal UI, which ends by itself
  when the agent stops. A role's runs are headless when its entry in
  `config/foundry.yaml` says `headless: true`; `--headless` and
  `--interactive` override that for one launch.
- **Interactive run**: an agent run in the human's terminal, which ends when
  the human exits it.
- **Live view**: what `foundry run` prints on stderr while a headless run
  works.

## Open questions
