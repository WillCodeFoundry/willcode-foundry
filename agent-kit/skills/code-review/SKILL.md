---
name: code-review
description: 'Review a task branch''s changes since it left the default branch along two axes: Standards (does the code follow the project''s documented coding standards?) and Spec (does the code do what the task''s TASK.md asks?). Runs both reviews in parallel sub-agents and writes them side by side as a round in REVIEW.md. Use when the reviewer role reviews a task.'
metadata:
  source:
    repo: mattpocock/skills
    path: skills/engineering/code-review
    commit: 5beb35b040e3de97e54fa9e386d7e42d15c295c2
    author: Matt Pocock
    license: MIT (see ../LICENSE-mattpocock-skills)
  adapted: for willcode-foundry, edited in place; see Skills in its README
---

Two-axis review of the diff between `HEAD` and the point where the task branch left the default branch:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the task's `TASK.md`?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

## Process

### 1. Pin the fixed point

The task branch was created from the default branch, so the fixed point is where it left it; there is nothing to ask. `git symbolic-ref --short refs/remotes/origin/HEAD` prints `origin/<default branch>`; the fixed point is

```bash
git merge-base HEAD origin/<default branch>
```

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside two parallel sub-agents.

### 2. Identify the spec source

The spec is the task's `TASK.md`, in the version your `ROLE.md`'s check settled on: the last one written by an allowed commit. Read that version from the notes checkout:

```bash
git -C "$AGENT_NOTES_DIR" show "<commit>:$AGENT_TASK_FILE"
```

If no allowed commit wrote one, the **Spec** sub-agent skips and reports "no spec available".

### 3. Identify the standards sources

In this order: the project's own `AGENTS.md` at the repository root first, since it wins for anything about the code (as `AGENTS.md` in the agent kit says); then `CODING_STANDARDS.md` or `CONTRIBUTING.md`, if present. Where they disagree, the earlier one wins.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### 4. Spawn both sub-agents in parallel

Issue both sub-agent calls together, in the foreground, and aggregate the reports they return.

**Standards sub-agent prompt** should include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, **plus the smell baseline from step 3** pasted in full (the sub-agent has no other access to it).
- The brief: "Report, per file/hunk where relevant, (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls: documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."

**Spec sub-agent prompt** should include:

- The diff command and commit list.
- The text of `TASK.md` from step 2, and the commit it came from.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report.

### 5. Aggregate

Write the result as a new round in the task's `REVIEW.md`, as your `ROLE.md`'s "Reviewing" section describes, with the two reports under `### Standards` and `### Spec` headings in the round, verbatim or lightly cleaned, each finding with its id. Do **not** merge or rerank findings, because the two axes are deliberately separate (see _Why two axes_).

End the reports with a one-line summary, before the round's verdict: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
