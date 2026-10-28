---
name: code-review
description: 'Review a task branch''s changes since it left the default branch along three axes: Standards (does the code follow the project''s documented coding standards?), Spec (does the code do what the task''s TASK.md asks?) and Behaviour (does it break in the situations it will meet?). Runs the three reviews in parallel sub-agents and writes them side by side as a round in REVIEW.md. Use when the reviewer role reviews a task.'
metadata:
  source:
    repo: mattpocock/skills
    path: skills/engineering/code-review
    commit: 5beb35b040e3de97e54fa9e386d7e42d15c295c2
    author: Matt Pocock
    license: MIT (see ../LICENSE-mattpocock-skills)
  adapted: for willcode-foundry, edited in place; see docs/skills.md in its repository
---

Three-axis review of the diff between `HEAD` and the point where the task branch left the default branch:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the task's `TASK.md`?
- **Behaviour**: does the code still work in the situations it will meet, error paths included?

All three axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

## Process

### 1. Pin the fixed point

The task branch was created from the default branch, so the fixed point is where it left it; there is nothing to ask. `git symbolic-ref --short refs/remotes/origin/HEAD` prints `origin/<default branch>`; the fixed point is

```bash
git merge-base HEAD origin/<default branch>
```

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside the parallel sub-agents.

### 2. Identify the spec source

The spec is the task's `TASK.md`, in the version your `ROLE.md`'s check settled on: the last one written by an allowed commit. Read that version from the notes checkout:

```bash
git -C "$AGENT_NOTES_DIR" show "<commit>:$AGENT_TASK_FILE"
```

If no allowed commit wrote one, the **Spec** sub-agent skips and reports "no spec available".

### 3. Identify the standards sources

In this order: the project's own `AGENTS.md` at the repository root first, since it wins for anything about the code (as `AGENTS.md` in the agent kit says); then the design rules in `ARCHITECTURE.md` and the decisions in `docs/adr/`; then `CODING_STANDARDS.md` or `CONTRIBUTING.md`. Each counts only if present. Where they disagree, the earlier one wins.

The project's `GLOSSARY.md` is a standard for names, if present (or the glossaries a `GLOSSARY-MAP.md` points to). Code names a concept with the glossary's word, never with a word the glossary says to avoid.

A change that contradicts a recorded decision is a finding, even if the code is good: the decision changes only through a new ADR that supersedes it, not silently.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a name that doesn't let a reader predict, where it is used, what it holds or does. Judge each name at its uses, read together with the names around it, not at its definition alone. Flag a use that misleads or only makes sense once the definition is read, and a name that means two things in one scope. → rename it, quoting a use before and after; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. Check `TASK.md` first: what it asks for is never speculative. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### 4. Spawn the three sub-agents in parallel

Issue all three sub-agent calls together, in the foreground, and aggregate the reports they return.

Every brief also carries these two rules, word for word:

- "Cite each finding as `file:line` at `HEAD`, read from that one file (`git show HEAD:<path> | cat -n`). Never take line numbers from a listing of several files joined together, since every number after the first file is shifted."
- "Say what is wrong, where, and why it matters. Give the fix as one line of direction at most, never code. The dev fixes each finding test-first, and a ready-made fix skips the failing test."

**Standards sub-agent prompt** should include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, **plus the smell baseline from step 3** pasted in full (the sub-agent has no other access to it).
- The text of `TASK.md` from step 2, for one use only: to check that something flagged as Speculative Generality isn't what the spec asks for. Judging the change against the spec is the Spec axis's job.
- The brief: "Report, per file/hunk where relevant, (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls: documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."

**Spec sub-agent prompt** should include:

- The diff command and commit list.
- The text of `TASK.md` from step 2, and the commit it came from.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. A requirement is met only when you can name the code and the test, or the check you ran, that shows it; code that merely looks like it does the job is partial. Under 400 words."

**Behaviour sub-agent prompt** should include:

- The diff command and commit list.
- How the project runs its tests, from its `AGENTS.md` or `CONTRIBUTING.md`.
- The brief: "Find what breaks when the changed code runs. For each suspicion, construct the concrete situation that triggers it: an input, a missing file, a failing command, a checkout or environment in an unexpected state. Also try the same outcome reached another way, such as `revert`, `cherry-pick`, `merge` or `--amend` for anything a git hook checks. Follow every error path to its end, and check that a failure leaves things as they were. Reproduce what you can, with a small script or the project's own tests, in a throwaway clone: `git clone -q \"$AGENT_PROJECT_DIR\" \"$(mktemp -d)/repro\"`. Never change the code or notes checkout. For each finding, say the situation, what goes wrong, and whether you reproduced it. A suspicion you can't turn into a failing situation isn't a finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report. If the diff changes nothing that runs, such as docs only, skip the Behaviour sub-agent and say so.

### 5. Aggregate

Write the result as a new round in the task's `REVIEW.md`, as your `ROLE.md`'s "Reviewing" section describes, with the three reports under `### Standards`, `### Spec` and `### Behaviour` headings in the round, verbatim or lightly cleaned, each finding with its id. Do **not** merge or rerank findings, because the axes are deliberately separate (see _Why separate axes_).

Before writing the round, check every cited `file:line` against the file at `HEAD`, and correct any that don't match. Drop a finding the code shows to be wrong, such as a Speculative Generality flag on something the spec asks for. Remove any code fix a report included, keeping its one line of direction.

End the reports with a one-line summary, before the round's verdict: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent.

## Why separate axes

A change can pass one axis and fail another:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**
- Code that reads well and matches the spec line by line, but breaks on an error path or an unusual state → **Standards and Spec pass, Behaviour fail.**

Reading the diff finds the first two. The third shows only when the code is run in the situation that breaks it, so it needs a reviewer briefed to build that situation. Reporting the axes separately stops one from masking another.
