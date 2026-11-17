# Log

## 1 · planner · progress
Done: the human asked to plan slice 2 of wcf-0035, "agent runs that end by themselves and report their unsaved work". Its agreed scope is wcf-0035's LOG entry 5, and the sbx facts behind it are in entries 2–4. wcf-0035 is not merged yet: its TURN is dev, and it has no PLAN.md. So this task needs `After: wcf-0035`. I read the launch path as it is on main today: `foundry run` → launch → attach, `sbx run` exec'd in place of foundry; the role options in config/foundry.yaml (only `model`, ADR-0014); and GLOSSARY's Launch, Agent run and Opening prompt. No follow-up in the notes touches the launch path.
Next: question round 1 with the human, on the three points entry 5 left open (live-view lines, unknown mode, both flags) and the gaps found while scoping. Then draft TASK.md.

## 2 · planner · progress
Done: settled with the human in rounds:
- Every role must name whether it runs headless; there is no default.
- The setting is `headless: true|false`, not a "mode". "Mode" would clash with GLOSSARY's Root mode and Agent mode, and the human declined renaming those.
- Shipped config: dev, reviewer and qa headless; planner and architect interactive.
- A bad or missing value is refused before any sandbox is touched.
- Giving both flags is a usage error.
- Live view on stderr, final message on stdout, then the exit report.
- On Ctrl-C, stop the agent, waiting up to 10 s, then report.
- Out of scope: a time limit, saving the live view, resuming, and starting the next role.
TASK.md approved by the human and written in 8b750eb.
Next: end the turn.

## 3 · planner · planned
Done: TASK.md has 11 criteria and 6 out-of-scope lines, and Open questions is empty. It is `After: wcf-0035`: AC4, AC7–AC10 build on wcf-0035's exit report and its refusal beside a running agent, so this task can't merge before wcf-0035 does. Its sbx facts are in wcf-0035's LOG entries 2–4.
Next: the dev writes PLAN.md. It changes how an agent run is driven, so it should go to the architect. If wcf-0035's plan is still unsettled, the dev may want to wait for it.
