# Task wcf-0035: Report unsaved work when an agent run ends

<!-- Part of: agent runs that end by themselves and report their unsaved work
(slice 1 of 2; slice 2, headless mode, is scoped in this task's LOG.md entry 5). -->

## Goal
`foundry run` hands the terminal to the sandbox and is gone, so nothing tells
the human whether the agent left work uncommitted or unpushed; they find out
only by looking, or lose it when the sandbox is removed. After every agent
run, `foundry run` should report the sandbox's unsaved work and where it is,
or why it can't tell, and it should never start a second agent beside a
running one. Headless runs, the next slice, will end with this same report.

## Acceptance criteria
- [ ] AC1: When the agent run ends with both checkouts saved, `foundry run`
      prints one line on stderr saying so, and exits 0.
- [ ] AC2: When the agent run ends with unsaved work, `foundry run` prints, for
      each checkout that has some, its name ("code checkout" or "notes
      checkout"), its path in the sandbox, its branch, and whether it has
      uncommitted changes, commits not pushed, or both. It exits 1.
- [ ] AC3: When it can't tell, `foundry run` prints "can't tell" with the
      reason, and exits 1. The reasons include: the sandbox is not running
      (it is not started again to check), an agent is still running in it, a
      checkout can't be read, and origin can't be reached. A comparison with
      the last fetched state is never reported as saved.
- [ ] AC4: The report follows every agent run `foundry run` attached, however
      it ended, including `sbx run` being killed while `foundry run` survives.
      A launch that fails before attaching prints its error as today, and no
      report.
- [ ] AC5: When an agent is already running in the sandbox, `foundry run`
      refuses to attach: it names the sandbox, gives a command that stops
      that agent, exits 1, and starts no second agent.
- [ ] AC6: While attached, the agent's terminal UI works as today: a single
      Ctrl-C only clears Claude Code's input, and resizing works.
- [ ] AC7: `README.md` says what `foundry run` reports after a run and its exit
      codes, and no doc still says foundry never learns how the run ended.

## Out of scope
- OS1: What stops an agent ending its turn with unsaved work: the agent's stop
  check keeps its behaviour, offline included.
- OS2: Running a role headless, a live view of it, and stopping it on Ctrl-C:
  the next slice.
- OS3: Starting the next role when a turn ends.
- OS4: foundry saving the work itself.
- OS5: Telling the human anywhere but the terminal `foundry run` ran in.
- OS6: A report when `foundry run` itself is killed: nothing of foundry
  survives to give it, and the agent may run on (LOG entries 2–3).

## Risks
- In probe O2, a sandbox was found stopped after its orphaned agent finished,
  which never followed a normal run. The cause is unknown, and it would turn
  a report into "can't tell".
- The probes (LOG entries 2–4, sbx v0.46.0) ran in throwaway sandboxes
  without foundry's kit or managed settings.
- The sbx tier stops before attaching an agent, so AC4 and AC6 may need
  checking by hand against real sbx.
- foundry's launch changes from replacing itself to waiting for the agent;
  the dev's plan should go to the architect.
- No existing follow-up touches this code.

## Terms
- **Unsaved work**: changes in a checkout that origin lacks: uncommitted
  changes, or commits not pushed to its branch. The agent's stop check and the
  exit report share this definition.
- **Exit report**: what `foundry run` prints after an agent run ends: each
  checkout's unsaved work, that both are saved, or why it can't tell.

## Open questions
