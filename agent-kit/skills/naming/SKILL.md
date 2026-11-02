---
name: naming
description: How to choose a name, record it, and judge it. Use when the dev or architect names a module, type, function, variable, parameter, field, file or option, when renaming one, when the dev records names in NAMES.md, and when the reviewer judges the names a change adds or renames.
---

# Naming

A name is good when a reader at one of its uses, with the names around it, can predict what it holds or does. This skill is the foundry's one statement of that test. The dev and the architect choose names by it, and the `code-review` skill judges them by it. The project's own `AGENTS.md` wins where it says otherwise.

## Where a name comes from

Take the first that has a word for the concept:

1. The project's `GLOSSARY.md`, or the glossaries a `GLOSSARY-MAP.md` points to. Never use a word it lists under _Avoid_ for that concept.
2. `DESIGN.md`, for the modules, interfaces and seams it names.
3. The code already there, found as "Check against the code" says. Keep its word rather than adding a synonym.
4. Otherwise a new word.

An instance of a class is named for its class, in the class's own words: an instance of `SomeOtherDependency` is `some_other_dependency`. That gives each type one spelling, so a reader knows the type from the name. Name it for its role instead only when:

- the scope holds two of the type, such as `recorded` and `wanted`;
- its role is what the reader needs, such as `destination` for the task being moved to.

Never name it with a word that says nothing, such as `result`, `obj` or `item`.

A concept the glossary lacks goes in `LEARNINGS.md` as a `[proposal]` entry, as the `domain-modeling` skill says. Don't add it to `GLOSSARY.md` yourself unless `TASK.md` or `DESIGN.md` lists it.

## Check against the code

Before choosing a name, and before judging one, search the whole repository with `git grep -n -w`: for the name, and for the other words a reader might use for the concept. Look for three things.

| Look for | What it is | What to do |
|---|---|---|
| A synonym | another word the code already uses for this concept | use that word instead |
| A homonym | this word, already used for a different concept | choose another word, so one word means one thing |
| An instance named otherwise | another instance of the same class, named neither for its class nor for one of the two reasons above | name yours for the class anyway |

The code's agreed word for a concept is the glossary's, then `DESIGN.md`'s, then the class's own name for its instances, then a word the code uses for that concept and nothing else. An instance named otherwise is drift, not agreement. Don't copy it, and don't rename it in this task: the dev lists it under `Next` in `LOG.md` as a suggested follow-up.

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

- The dev: a module or interface `DESIGN.md` names is the architect's. Ask the architect, as "When to stop and ask" in `AGENTS.md` says. Anything smaller, split it.
- The reviewer: label it a Design question when the fix would change what `DESIGN.md` decides.

## NAMES.md

The dev records its naming decisions in the task's `NAMES.md`, in `$AGENT_NOTES_DIR/$AGENT_TASK_NOTES_DIR/`. Only the dev writes it. It has one row for each name the task's code adds or renames, kept current: when a name changes again, change its row, and remove the row of a name the code no longer has.

```markdown
# Names

| Name | Kind | Where | Evidence |
|---|---|---|---|
| `project_tasks` | variable | `src/app/run.py` | Instance of `ProjectTasks`. `cli.py:40` names one `tasks`: drift, noted in LOG.md. |
| `close` (was `finish`) | method | `src/app/task.py` | GLOSSARY.md: Closed task. `finish` already means a session ending, `session.py:88`. |
| `TaskMover` | type | `src/app/move.py` | DESIGN.md, "Modules and seams". |
| `relaunch` | function | `src/app/run.py` | New word. No synonym found for: restart, resume, reopen. |
```

- **Name**: the name, with its old name for a rename.
- **Kind**: function, method, type, variable, parameter, field, file or option.
- **Evidence**: where the word comes from, by "Where a name comes from": the glossary entry, the `DESIGN.md` section, or existing uses as `file:line`. For a new word, the words you searched for. Add any synonym, homonym or drift the search found.

## Before each commit

The dev lists every name the staged diff (`git diff --cached`) adds or renames. Check each against the code, and read it at one of its uses by the test. Fix any that fails. Then add or change its row in `NAMES.md`, and commit that with the step's `LOG.md` entry.

## Reviewing names

The reviewer judges names in the `code-review` skill's Smells axis, starting from `NAMES.md`. It judges only the names the diff adds or renames. A poor name the diff didn't add or rename isn't reported.

1. For each row, check that its evidence says what the row claims: open the glossary entry, the `DESIGN.md` section, or the uses it cites.
2. List the names the diff adds or renames that have no row.
3. Check each name against the code, and read it at its uses by the test.

Report a name only when it meets this bar:

| The name | Finding |
|---|---|
| misleads at a use, by "The test" | Blocking |
| breaks a word the codebase already agrees on: a synonym for the agreed word, a homonym, or an instance named otherwise | Blocking |
| needs a change to what `DESIGN.md` decides, to fix either of those | Design question |
| passes both, but could be better | not reported |

Names with no row in `NAMES.md` are one Follow-up, listing them. They are judged like any other name.
