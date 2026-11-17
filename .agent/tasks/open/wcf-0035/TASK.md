# Task wcf-0035: Report unsaved work when an agent run ends

<!-- Part of: agent runs that end by themselves and report their unsaved work
(slice 1 of 2; slice 2, headless mode, is scoped in this task's LOG.md entry 5). -->

## Goal
`foundry run` hands the terminal to the sandbox and is gone, so nothing tells
the human whether the agent left work uncommitted or unpushed; they find out
only by looking, or lose it when the sandbox is removed. After every agent
run, `foundry run` should report the sandbox's unsaved work and where it is,
or why it can't tell, and it should never start a second agent beside a
running one. Headless runs, the next slice, will end with this same checkout
status. Amended: D2. Because: the term was renamed.

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
- [ ] AC8: When origin can't be reached, the agent's stop check blocks the
      agent's stop, its reason saying "can't tell" because origin can't be
      reached, where it compared with the last fetched state before. The
      agent's next stop goes through, as after any block. Amended: D1.
      Because: the stop check and the checkout status share one definition
      of unsaved work, and a hook that enforces a rule blocks when it can't
      check it (DR6).

## Out of scope
- OS1: Any other change to when the agent's stop check blocks a stop: it
  blocks exactly when it does today, but for AC8. Amended: D1. Because: the
  human chose that the stop check also blocks when origin can't be reached.
- OS2: Running a role headless, a live view of it, and stopping it on Ctrl-C:
  the next slice.
- OS3: Starting the next role when a turn ends.
- OS4: foundry saving the work itself.
- OS5: Telling the human anywhere but the terminal `foundry run` ran in.
- OS6: A report when `foundry run` itself is killed: nothing of foundry
  survives to give it, and the agent may run on (LOG entries 2–3).
- OS7: A command that shows the checkout status without starting an agent:
  a follow-up the human agreed to in the dev's session (LOG entry 12).

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
- The only follow-up on this code is LOG entry 12's, put out of scope as OS7.

## Terms
- **Unsaved work**: changes in a checkout that origin lacks: uncommitted
  changes, or commits not pushed to its branch. The agent's stop check and the
  checkout status share this definition. Amended: D2. Because: the term was
  renamed.
- **Checkout status**: what `foundry run` reports after an agent run ends:
  each checkout's unsaved work, that both are saved, or why it can't tell.
  Amended: D2. Because: it names what is checked, both checkouts, rather than
  when, so a later check-only command can share it.

## Open questions
