---
name: naming
description: How to choose a name, and how to judge one. Use when the dev or architect names a module, type, function, variable, parameter, field, file or option, when renaming one, and when the reviewer judges the names a change introduces.
---

# Naming

A name is good when a reader at one of its uses, with the names around it, can predict what it holds or does. This skill is the foundry's one statement of that test. The dev and the architect choose names by it, and the `code-review` skill judges them by it.

## Where a name comes from

Take the first that has a word for the concept:

1. The project's `GLOSSARY.md`, or the glossaries a `GLOSSARY-MAP.md` points to. Never use a word it lists under _Avoid_ for that concept.
2. `DESIGN.md`, for the modules, interfaces and seams it names.
3. The code already there: search it for the concept before naming it again. Keep its word rather than adding a synonym.
4. Otherwise a new word, which you record as below.

A concept the glossary lacks goes in `LEARNINGS.md` as a `[proposal]` entry, as the `domain-modeling` skill says. Don't add it to `GLOSSARY.md` yourself unless `TASK.md` or `DESIGN.md` lists it.

## The test

Judge a name at its uses, never at its definition alone. Read each use as a sentence, with the names beside it. A name fails when a use:

- only makes sense once you have read the definition;
- reads as a different kind of thing than it is: a condition that isn't a boolean, a collection that isn't one, a value that is an action;
- reads true where the code makes it false, or the reverse;
- promises less than the code does. A name that reads as a lookup must not write, switch a checkout, call out over the network, or fail where absence is normal. Its verb is a promise about cost, side effects and failure;
- shares its word with something else in the same scope, or sits one letter from a name that means something else;
- names the type, or the step that produced the value, instead of what the value is in the domain.

When you rename, read every use of the name, not only those in your diff. A use outside the diff can change meaning too.

## When no honest name comes

A thing that has no honest name is doing more than one job, or the design is unclear. Don't cover it with a word that says nothing about the job, such as manager, helper, data, info, util or handler. Split it, or raise it:

- The dev: a module or interface `DESIGN.md` names is the architect's. Stop and ask, as "When to stop and ask" in `AGENTS.md` says. Anything smaller, split it.
- The reviewer: label it a Design question when the fix would change what `DESIGN.md` decides.

## Before each commit

The dev lists every name the diff introduces or renames, from `git diff --cached`. Read each at one of its uses, by the test above. Fix any that fails before committing.
