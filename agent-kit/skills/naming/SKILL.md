---
name: naming
description: How to choose a name, and how to judge one. Use when the dev or architect names a module, type, function, variable, parameter, field, file or option, when renaming one, and when the reviewer judges the names a change introduces.
---

# Naming

A name is good when a reader at one of its uses, with the names around it, can predict what it holds or does. This skill is the foundry's one statement of that test. The dev and the architect choose names by it, and the `code-review` skill judges them by it. The project's own `AGENTS.md` wins where it says otherwise.

## Where a name comes from

Take the first that has a word for the concept:

1. The project's `GLOSSARY.md`, or the glossaries a `GLOSSARY-MAP.md` points to. Never use a word it lists under _Avoid_ for that concept.
2. `DESIGN.md`, for the modules, interfaces and seams it names.
3. The code already there: search it for the concept before naming it again. Keep its word rather than adding a synonym.
4. Otherwise a new word, which you record as below.

An instance of a class is named for its class, in the class's own words: an instance of `SomeOtherDependency` is `some_other_dependency`. That gives each type one spelling, so a reader knows the type from the name. Name it for its role instead only when:

- the scope holds two of the type, such as `recorded` and `wanted`;
- its role is what the reader needs, such as `destination` for the task being moved to.

Never name it with a word that says nothing, such as `result`, `obj` or `item`.

A concept the glossary lacks goes in `LEARNINGS.md` as a `[proposal]` entry, as the `domain-modeling` skill says. Don't add it to `GLOSSARY.md` yourself unless `TASK.md` or `DESIGN.md` lists it.

## The test

Judge a name at its uses, never at its definition alone. Read each use as a sentence, with the names beside it.

A name's grammar matches its kind: a noun phrase for a value, a question for a boolean, a verb for a function. Words such as is, has, can, should, if and when start only booleans. Name a value for what it is, not for the situation it belongs to.

A name fails when a use:

- only makes sense once you have read the definition;
- reads as a different kind of thing than it is: a condition that isn't a boolean, a collection that isn't one, a value that is an action;
- reads true where the code makes it false, or the reverse;
- promises less than the code does. A name that reads as a lookup must not write, switch a checkout, call out over the network, or fail where absence is normal. Its verb is a promise about cost, side effects and failure;
- shares its word with something else in the same scope, or sits one letter from a name that means something else;
- names the type, or the step that produced the value, instead of what the value is in the domain.

When you rename, read every use of the name, not only those in your diff. A use outside the diff can change meaning too.

## In Python

These apply when the project is in Python. Leave case and builtin shadowing to the project's linter.

- Don't repeat the module in a name. Callers read `task.Status`, so `TaskStatus` says "task" twice.
- A property is a noun, cheap, and without side effects. Anything that does I/O, changes state or can fail is a method, named with a verb.
- Parameter names are part of the interface, since callers can pass them by keyword. Renaming a public one changes the interface, so it follows `DESIGN.md` when that decides the interface.
- A leading underscore means nothing outside the module or class uses the name. Give it to every name only used inside, and to no name used outside.
- An exception is named for what happened, in the glossary's words when it has one.
- A dict is named for its key and value: `task_by_id`, not `tasks` or `lookup`.

## When no honest name comes

A thing that has no honest name is doing more than one job, or the design is unclear. Don't cover it with a word that says nothing about the job, such as manager, helper, data, info, util or handler. Split it, or raise it:

- The dev: a module or interface `DESIGN.md` names is the architect's. Stop and ask, as "When to stop and ask" in `AGENTS.md` says. Anything smaller, split it.
- The reviewer: label it a Design question when the fix would change what `DESIGN.md` decides.

## Before each commit

The dev lists every name the diff introduces or renames, from `git diff --cached`. Read each at one of its uses, by the test above. Fix any that fails before committing.
