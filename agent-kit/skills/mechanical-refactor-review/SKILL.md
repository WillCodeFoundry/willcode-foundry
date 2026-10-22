---
name: mechanical-refactor-review
description: Senior-developer review of any codebase or branch, in any language, focused on naming, module and package structure, single responsibility, ports and adapters, DRY, trivial helpers and over-defensive code, ending in an agreed, mechanical refactor brief another agent can implement. Use whenever the user asks for a code review "as a senior developer", wants to find code smells, simplify or reduce complexity, clean up names or module structure, check hexagonal or clean architecture, or wants a refactor plan or brief to hand to another agent, even if they don't say "mechanical" or "brief".
compatibility: scripts/rank-complexity needs uv and network access to PyPI; the rest of the skill needs only a shell and git.
---

# Mechanical refactor review

Review code the way a senior developer would before a refactor. Then agree a change proposal with the user. Then write a brief that another agent can implement without reopening decisions.

This works for any repository and any language. The examples in `references/checklist.md` use Python-like syntax only for illustration; apply the same ideas in the conventions of the language you're reviewing.

**If the code is Python, also read `references/python.md`.** It covers Python's tools, idioms and the forms each smell takes in Python.

**If the scope includes tests,** or the brief will change code under test (almost always), **also read `references/testing.md`.** It covers stubs, fakes and mocks; injecting dependencies rather than patching; and how test findings shape the brief.

The work runs in five stages. Do them in order, and **stop for the user's agreement at the end of stages 3 and 4**. Names and scope are the user's call: propose them with reasons, don't impose them.

## Stage 1: Get the latest code and read all of it

- **Get the current state.**
  - For a remote branch, fetch it fresh every round, and state the commit you reviewed. Other people or agents may have pushed since the last round; if new commits arrived, say what they changed before reviewing again.
  - For a local working tree, note the branch and whether there are uncommitted changes.
- **Agree the scope.** By default review the whole branch against its base, or the whole codebase if there's no branch. If the user means only the newest changes, or only some directories, use that. If the request is ambiguous, ask once.
- **Read every file in scope in full,** including scripts and configuration that behave like code. Read the test doubles too (fakes, mocks, stubs): they are the best evidence of where the real seams are (see the checklist).
- **Rank where to look first.**
  - Run `scripts/rank-complexity <paths…>` (any language). It lists the most complex functions by cyclomatic complexity, using lizard at the version pinned in this skill's `requirements.txt`.
  - For Python, also run `scripts/rank-complexity --cognitive <paths…>`. Cognitive complexity weights nesting, so it shows functions that are hard to read rather than merely branchy. The tools in `references/python.md` add more.
  - If `uv` or PyPI isn't available, use the project's own linter complexity rule, or count branches by eye in the largest functions.
  - Use the ranking to decide where to read first. It is not a finding in itself.
- **Run the project's own checks** (tests, linters, type checker, build) if you can. If the environment blocks them, say so in one line and carry on.

## Stage 2: Review against the checklist

Read `references/checklist.md` and apply every section. These are its core rules:

- **Report only realistic problems.** Drop any edge case that needs an unusual input or an unlikely sequence of events. If you're unsure whether something is realistic, leave it out or mention it in one line at the end.
- **Prefer loud failure to defensive code.** A clear error naming the file or input beats validating every possible shape. Recommend documenting an assumption over defending against its violation.
- **Back every finding with evidence:** a file and line, a call count, a search result, or a reproduction. Verify any claim you can check cheaply, and say "verified" when you did.
- **Say what's good, briefly.** A review that only lists faults hides which parts should be left alone.

Structure the review by theme, ordered by how much each theme matters. For each finding give the location, the problem, and the suggested change. End with an order of work.

## Stage 3: Reduce expectations before refactoring

Before proposing any restructuring, ask of each check, rule, guard or validation: **does it catch a realistic mistake that nothing else catches?**

- Look for anything else that already enforces the same thing: a server-side or platform rule, the type system, a database constraint, a CI check, or a failure that would be loud on its own.
- Wherever code analyses arbitrary input to decide whether it conforms (parsing config files, workflow definitions, command lines, documents), consider **comparing against a template** instead. The user then owns the template, and the code shrinks to a fetch, a normalise and a diff.
- Present this as a table: rule, what else enforces it, keep, drop or replace, and why. Give rough before and after line counts.
- Let the user decide judgement calls. Name the trade-off without arguing for one side, and record whichever way they choose.

Simplifying first often removes code that would otherwise need refactoring, so this stage comes before stage 4.

## Stage 4: Agree a mechanical change proposal

"Mechanical" means renames, moves, inlining, and replacing defensive checks with loud failures, with **no other behaviour change**. List any unavoidable behaviour change explicitly, such as a changed output format or error message.

Before proposing changes, establish the safety net:

- **Coverage:** do tests exercise the code to be renamed or moved? Where they don't, the brief's first step adds characterisation tests that pin the current behaviour.
- **Public versus internal:** in a library or service with external consumers, a renamed public name or endpoint needs a deprecation alias or a versioned change. In an application, renames are internal. State which case applies.
- **Tests coupled to structure:** patches of import paths or private functions break on moves. List every patch target the brief changes; those tests are updated in the same commit as the move. Replacing patching with injection changes signatures, so it belongs in the structural step that follows (`references/testing.md`, section 8).

Build the proposal in this order:

1. **A glossary first.** Most naming problems come from overlapping nouns. Define each domain term once (what it means, and which module owns it), then derive the names from it. Prefer terms the project's own docs and users already use.
2. **Conventions:** a few rules that decide many names at once. For example, `_dir` for directories and `_path` for files, or `ensure_` makes something so while `require_` checks and raises. Follow the language's established naming style, and note exceptions as you find them, with the reason.
3. **Rename tables,** grouped by module: current name, proposed name, and why.
4. **Moves:** what goes where, and what each moved thing must no longer know.
5. **Inlines:** each helper, and its single call site.
6. **Defensive code replaced by loud failures:** where, now, and new.
7. **Out of scope:** the structural changes deferred to a later step.
8. **Open choices,** each with a recommendation and its alternatives.

When discussing a name:
- Say what the thing does and what it's for, then derive the name from that.
- Offer one recommendation, plus a short table of rejected alternatives with the problem each one has.
- If the user rejects a name, ask what it misses, then re-derive. Don't just offer synonyms.
- Check every new name against the glossary. A new name must not reintroduce a word the glossary deliberately left out.

## Stage 5: Write the implementer brief

Read `references/brief-template.md` and follow it. The brief is the single source of truth for the implementer:

- Record decisions as decided, with their reasons, so the implementer applies them consistently and doesn't reopen them.
- Give the exact old and new names, the new module layout, and the new output format where it changes.
- Include a "done when" list with the project's checks, plus search patterns for every old name that must disappear.
- Split the work into small commits that each keep tests, lint and types green, and ask for commit messages that say why.
- Recommend the language's rename tooling (an IDE refactor, or equivalent) over text replacement for names that are also common words.

Deliver the brief as a Markdown file.

**When the implementer raises concerns:**
- Weigh each concern against the glossary and conventions. Accept it when it's more consistent with them, which is often.
- Update the brief itself, so it stays the single source of truth.
- Re-send the brief, and summarise what changed in a line or two.

## Output style

- **Reviews and proposals go in the conversation.** They are read once and discussed.
- **Briefs and anything the user asks to keep go in files.**
- Use tables for rename lists and rule-by-rule decisions, and prose for reasoning.
- Don't recap the process at the end. Say what came out, and the one decision the user needs to make next.
