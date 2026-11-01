# Roles talk through an append-only log, and route by outcome

Each task notes file now has one writer, or only grows. `TASK.md`, `DESIGN.md` and `REVIEW.md` are their owners' alone. Everything roles tell each other goes in `LOG.md`: numbered entries each role appends, and none changes once pushed. `pre-commit` refuses a change to what origin has, and a new entry headed with another role or numbered out of turn. Entries are numbered, not dated: git already records when each line was written, a number lets an answer cite an entry, and a role writing against a stale copy of the log gets it wrong. `PROGRESS.md`, which every role rewrote, is gone: a role could drop another's open question, or the line answering it, without anyone seeing.

A role ends its turn with an outcome from its `ROLE.md`. One table in `agent-kit/AGENTS.md` maps each role and outcome to the next turn, where each `ROLE.md` used to name it. Roles still write `TURN`, so [ADR 0011](0011-turn-is-one-line.md) stands; only where they look it up changed. A role decides what to do from what the notes show is open, never from who had the turn before it: a detour through the planner can then lose nothing.

## Considered options

- **A file per role.** Ownership is by file, with no new hook. But a question and its answer sit in different files, and their order is rebuilt across four.
- **Outcomes as commit trailers.** One per turn and signed, but read with `git log` rather than as a file.
- **Routing in foundry, from an outcome file.** The turn could never be miswritten, but it reverses ADR 0011 for a mistake you see at the next launch.
