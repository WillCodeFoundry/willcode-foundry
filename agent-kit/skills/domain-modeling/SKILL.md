---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when the planner settles terms and decisions with the human, when the dev applies TASK.md's "Terms and decisions" to GLOSSARY.md or docs/adr/, or when any role finds a term or decision worth recording.
metadata:
  source:
    repo: mattpocock/skills
    path: skills/engineering/domain-modeling
    commit: 5beb35b040e3de97e54fa9e386d7e42d15c295c2
    author: Matt Pocock
    license: MIT (see ../LICENSE-mattpocock)
  adapted: for willcode-foundry, edited in place; see Skills in its README
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline: challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise. (Merely *reading* `GLOSSARY.md` for vocabulary is not this skill: that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

**Who writes what.** Only the planner talks with the human, so the challenges below happen in planner sessions, and what they settle goes into the task's `TASK.md`, under "Terms and decisions", not into the project's files. The dev writes to the project's `GLOSSARY.md` and `docs/adr/`, on the task branch, exactly what that section lists, and nothing else. Any other term or decision a role thinks deserves recording goes in `LEARNINGS.md` as a `[proposal]` entry; a question that blocks the work follows "When to stop and ask" in `AGENTS.md`.

## File structure

Most repos have a single context:

```
/
├── GLOSSARY.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If a `GLOSSARY-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives:

```
/
├── GLOSSARY-MAP.md
├── docs/
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── GLOSSARY.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── GLOSSARY.md
│       └── docs/adr/
```

Create files lazily: only when you have something to write. If no `GLOSSARY.md` exists, create one when the first term is resolved. If no `docs/adr/` exists, create it when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `GLOSSARY.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account': do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Record terms as they're resolved

The planner: when a term is resolved with the human, add it under "Terms and decisions" in the `TASK.md` draft right there, saying which `GLOSSARY.md` it goes in, with its entry in the format in [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md). Don't batch these up: capture them as they happen.

The dev: write each term that section lists into the `GLOSSARY.md` it names, in the same format. A term you think is missing or wrong goes in `LEARNINGS.md` as a `[proposal]` entry, not in `GLOSSARY.md`.

`GLOSSARY.md` should be totally devoid of implementation details. Do not treat `GLOSSARY.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer an ADR when all three are true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR.

The planner offers it to the human; once they agree, it goes under "Terms and decisions" in the `TASK.md` draft as a decision to record as an ADR, with its context, the decision and the alternatives rejected. The dev writes each ADR that section lists into `docs/adr/`, in the format in [ADR-FORMAT.md](./ADR-FORMAT.md). Any other decision you think meets all three goes in `LEARNINGS.md` as a `[proposal]` entry.
