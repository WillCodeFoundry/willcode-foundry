---
name: code-review
description: 'Review a task branch''s changes since it left the default branch along four axes: Standards (does the code follow the project''s documented coding standards?), Spec (does the code do what the task''s TASK.md and DESIGN.md ask?), Behaviour (does it break in the situations it will meet?) and Smells (did the change leave its functions simpler or more tangled?). Runs the four reviews in parallel sub-agents and writes them side by side as a round in REVIEW.md. Use when the reviewer role reviews a task.'
metadata:
  source:
    repo: mattpocock/skills
    path: skills/engineering/code-review
    commit: 5beb35b040e3de97e54fa9e386d7e42d15c295c2
    author: Matt Pocock
    license: MIT (see ../LICENSE-mattpocock-skills)
  adapted: for willcode-foundry, edited in place; see docs/skills.md in its repository
---

Four-axis review of the diff between `HEAD` and the point where the task branch left the default branch:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the task's `TASK.md`, and its `DESIGN.md` when it has one?
- **Behaviour**: does the code still work in the situations it will meet, error paths included?
- **Smells**: did the change leave each function it touches simpler, or more tangled?

All four axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

Each finding is **Blocking**, a **Follow-up** or a **Design question**, against a bar for its own axis (step 5). Blocking findings and design questions hold the verdict, so a round can approve with follow-ups open.

## Process

### 1. Pin the fixed point

The task branch was created from the default branch, so the fixed point is where it left it; there is nothing to ask. `git symbolic-ref --short refs/remotes/origin/HEAD` prints `origin/<default branch>`; the fixed point is

```bash
git merge-base HEAD origin/<default branch>
```

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside the parallel sub-agents.

**From round 2 on, review the fixes, not the branch again.** Round 1 reviews the whole diff. Later rounds take two things from `REVIEW.md`:

- the commit the last round reviewed, from its heading;
- every finding that is closed, accepted as is or deferred: the settled list.

Capture the fix diff, `git diff <last reviewed commit>...HEAD`. The sub-agents judge each open finding, and look for new problems only in the lines the fix diff touches. Code an earlier round reviewed and no fix touched isn't reviewed again.

The settled list holds findings, never code. Code and names a fix introduced are new surface for this round, even in a round that focuses on one concern.

After an architect turn, the fix diff includes `DESIGN.md`'s diff since the last round. Settle each design question it answers, and judge again each finding that waited for the design, against the new `DESIGN.md`.

### 2. Identify the spec source

The spec is the task's `TASK.md`, in the version your `ROLE.md`'s check settled on: the last one written by an allowed commit. Read that version from the notes checkout:

```bash
git -C "$AGENT_NOTES_DIR" show "<commit>:$AGENT_TASK_FILE"
```

If no allowed commit wrote one, the **Spec** sub-agent skips and reports "no spec available".

When the task has a `DESIGN.md`, the architect's design agreed with the human, it is part of the spec too. Read it from the notes checkout, beside `TASK.md`.

### 3. Identify the standards sources

In this order: the project's own `AGENTS.md` at the repository root first, since it wins for anything about the code (as `AGENTS.md` in the agent kit says); then the design rules in `ARCHITECTURE.md` and the decisions in `docs/adr/`; then `CODING_STANDARDS.md` or `CONTRIBUTING.md`. Each counts only if present. Where they disagree, the earlier one wins.

The project's `GLOSSARY.md` is a standard for names, if present (or the glossaries a `GLOSSARY-MAP.md` points to). Code names a concept with the glossary's word, never with a word the glossary says to avoid.

A change that contradicts a recorded decision is a finding, even if the code is good: the decision changes only through a new ADR that supersedes it, not silently.

### 4. The smell baseline

The Smells axis carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **A heuristic, not a rule.** Label each smell as one ("possible Feature Envy"). Skip anything tooling already enforces. Whether it blocks is the Smells bar's call, in step 5.

Each smell reads *what it is* → *how to fix*:

- **Long Function**: a function that does several things at different levels of detail, such as building what it needs and also deciding what to do with it. A function that grows a few lines per change never looks long in one diff, so judge it whole. Flag it when you can name two or more steps in it that would read better as functions of their own, with honest names, and name the function's problem, not only a symptom such as a stray variable. → extract those steps, so each can be tested on its own.
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

### 5. Spawn the four sub-agents in parallel

Issue all four sub-agent calls together, in the foreground, and aggregate the reports they return.

Every brief also carries these rules, word for word:

- "Cite each finding as `file:line` at `HEAD`, read from that one file (`git show HEAD:<path> | cat -n`). Never take line numbers from a listing of several files joined together, since every number after the first file is shifted."
- "Say what is wrong, where, and why it matters. Give the fix as one line of direction at most, never code. The dev fixes each finding test-first, and a ready-made fix skips the failing test."
- "Label each finding Blocking, Follow-up or Design question, by your axis's bar below and the design-question test after it. Everything that misses the bar is a Follow-up."
- "Say who would hit each finding, doing what, and how often. Drop a finding nobody realistic would hit."
- "Direct the smallest fix. 'Accept as is' is a valid direction. If the only fix you see adds machinery, or instructions that script a recovery, label it a Design question: that is for the architect and the owner, not a fix."
- "Report at most five findings, most important first. Fewer, or none, is a good result."

The bar for Blocking, each brief carrying its own axis's:

- **Standards:** the breach would lead a reader, human or agent, into a wrong action. That covers an instruction that contradicts the code or another instruction, a name that misleads where it is used, a contradicted ADR, or a broken design rule.
- **Spec:** a requirement is missing or wrong, or the change does something `TASK.md` rules out or departs from a decision in `DESIGN.md`.
- **Spec, partial:** a requirement the change doesn't show met, by the code and the test or check that shows it, is Blocking too.
- **Behaviour:** the failure is reproduced on a plausible path, and it loses work, does the wrong thing, or leaves something stuck without a message.
- **Smells:** the diff introduces the smell, or makes worse one the code already had, and its fix is local: one or two functions, with no change to an interface `DESIGN.md` decides. A smell the diff only touches is a Follow-up.

Any axis's finding is a **Design question** instead when its fix isn't a fix the dev can make alone:

- its fix would change a decision in `DESIGN.md`: an interface, a module boundary or a type;
- `DESIGN.md` asks for something a documented rule forbids;
- one decision causes the same smell more than once;
- no honest local fix exists.

From round 2 on, every brief also carries the fix diff command, the open findings to judge, and the settled list, with this rule: "Don't raise a settled finding again. Look for new problems only in the lines the fix diff touches."

**Standards sub-agent prompt** should include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3.
- The brief: "Report, per file/hunk where relevant, every place the diff violates a documented standard: cite the standard (file + the rule). Code smells are another axis's job. Skip anything tooling enforces. Under 400 words."

**Spec sub-agent prompt** should include:

- The diff command and commit list.
- The text of `TASK.md` from step 2, and the commit it came from, and the text of `DESIGN.md` when the task has one.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. A requirement is met only when you can name the code and the test, or the check you ran, that shows it; code that merely looks like it does the job is partial, and every partial requirement is a finding. Under 400 words."

**Behaviour sub-agent prompt** should include:

- The diff command and commit list.
- How the project sets up its environment and runs its tests, from its `AGENTS.md` or `CONTRIBUTING.md`: the setup commands as well as the test commands, since a fresh clone has neither its dependencies nor its tools.
- The brief: "Find what breaks when the changed code runs. For each suspicion, construct the concrete situation that triggers it: an input, a missing file, a failing command, a checkout or environment in an unexpected state. Also try the same outcome reached another way, such as `revert`, `cherry-pick`, `merge` or `--amend` for anything a git hook checks. Follow every error path to its end, and check that a failure leaves things as they were. Reproduce what you can, with a small script or the project's own tests, in a throwaway clone: `git clone -q \"$AGENT_PROJECT_DIR\" \"$(mktemp -d)/repro\"`. Run the project's setup commands in that clone before its tests. Never change the code or notes checkout. For each finding, say the situation, what goes wrong, and whether you reproduced it. A suspicion you can't turn into a failing situation isn't a finding. Before building a situation, say who causes it and how often. Skip anything that needs a deliberate bypass, or two actors within the same few seconds. Under 400 words."

**Smells sub-agent prompt** should include:

- The diff command, the commit list and the fixed point.
- The smell baseline from step 4, pasted in full (the sub-agent has no other access to it).
- The text of `TASK.md` and, when the task has one, `DESIGN.md`. `TASK.md` is for one use: to check that something flagged as Speculative Generality isn't what the spec asks for. `DESIGN.md` is for telling a local fix from a design question.
- The brief: "Read each function the diff adds or changes whole, three ways. At `HEAD`. Against its version at the fixed point (`git show <fixed point>:<path>`), asking whether the change left it simpler or more tangled; a regression counts even when each hunk looks fine. And beside its siblings in the diff, and any existing code whose shape it copies. Match each against the smell baseline. First list every function the diff adds or changes, as `file:function`, each marked 'clean', 'new' when it has no earlier version, or with its finding ids. Then report the findings. For this axis, 'who would hit it' is the next dev who changes that code, and 'fewer, or none, is a good result' doesn't apply: cover every function. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report. If the diff changes nothing that runs, such as docs only, skip the Behaviour and Smells sub-agents and say so.

### 6. Aggregate

Write the result as a new round in the task's `REVIEW.md`, as your `ROLE.md`'s "Reviewing" section describes, with the four reports under `### Standards`, `### Spec`, `### Behaviour` and `### Smells` headings in the round, verbatim or lightly cleaned, each finding with its id. Do **not** merge or rerank findings, because the axes are deliberately separate (see _Why separate axes_).

Before writing the round, check every cited `file:line` against the file at `HEAD`, and correct any that don't match. Drop a finding the code shows to be wrong, such as a Speculative Generality flag on something the spec asks for. Remove any code fix a report included, keeping its one line of direction.

Check the Smells coverage list against the diff: every function it adds or changes must be listed. Ask the sub-agent again for any that are missing.

Check each label against its axis's bar, and downgrade a Blocking finding that misses it. Drop a finding that raises a settled one again. Where two axes find one cause, keep both, each saying it shares a cause with the other. Never drop a finding because `DESIGN.md` decides it: label it a Design question.

List every Design question in its own `### Design questions` section, after the four reports. Each names its finding id, and the `DESIGN.md` decision or documented rule it puts in question. Mark each other finding whose fix depends on one "Waits for the design".

End the reports with a one-line summary, before the round's verdict: findings per axis, how many block, how many design questions are open, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent.

## Why separate axes

A change can pass one axis and fail another:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**
- Code that reads well and matches the spec line by line, but breaks on an error path or an unusual state → **Standards and Spec pass, Behaviour fail.**
- Code that keeps every rule, does what was asked and works, but leaves a function doing three jobs where it did one → **Standards, Spec and Behaviour pass, Smells fail.**

Reading the diff finds the first two. The third shows only when the code is run in the situation that breaks it, so it needs a reviewer briefed to build that situation. The fourth shows only when each changed function is read whole, and against its earlier version, so it needs its own reviewer and its own budget: sharing one with the documented standards, it lost to them. Reporting the axes separately stops one from masking another.

## Why a bar, and why later rounds review only the fixes

Fresh reviewers always find something. Without a bar, every finding holds the verdict, so a round approves only when it finds nothing, and it rarely will. Without a scope, each round sweeps the whole branch again, including the last round's fixes, and each fix is new surface to find fault with. The bar ends a review once nothing blocks. The scope stops each fix from opening a new round on code already settled.

A design question is neither. The dev can't fix it alone, and a Follow-up would let it through. So it goes to the architect, who settles it with the owner before the dev fixes anything that waits for it.
