---
name: python-refactoring-tasks
description: Hunt a Python codebase for refactors that make it simpler, and write a TASK.md for each one worth doing, on its own or from given hints such as follow-ups. Use when asked to find refactors or simplify.
---

# Finding refactoring opportunities in Python

Find changes across a Python codebase that make it simpler to read, test and change, and write a `TASK.md` for each one worth doing. You change no code. Nobody checks in with you along the way: you decide what is worth a task, and the human decides which tasks to create. A change counts only if it removes something: lines, branches, parameters, concepts, or a workaround in a test. Writing no task is a good result when nothing clears the bar.

This skill decides where to look and how to propose. What to look for comes from two skills:

| Skill | Use it for |
|---|---|
| `python-smells` | its checklist, questions 1–11, and the reference each "yes" points to |
| `python-naming-smells` | every name in the code you read, against the glossary's words |

Both are written for reviewing a diff. Here, apply them to existing functions and modules: treat the code you read as if it were the diff.

## Two ways to start

| You are given | Do |
|---|---|
| Nothing but the codebase | Find your own candidates: steps 1 and 2, then 3 onwards. |
| Hints: follow-ups or other notes naming places, each with a smell or a cost | Start from the hints (step 0), then run steps 1 and 2 as well, more lightly, so you don't see only what others saw. |

Use only the hints you are given. Don't go looking for follow-ups or notes yourself; collecting them is someone else's job.

## Before you start

- Read the project's own rules: `AGENTS.md`, `CONTRIBUTING.md`, the design rules in `ARCHITECTURE.md`, `GLOSSARY.md`, `docs/adr/`. A recorded decision is not a smell; propose superseding it only with a reason.
- Read `pyproject.toml`: the ruff rules selected and their thresholds, `per-file-ignores`, mypy's settings, vulture's whitelist.
- Run the project's checks once, so you know they pass before you start: `ruff check`, `ruff format --check`, `mypy`, `pytest`.

## 0. When given hints: check each one

A hint was written against older code, by someone looking at something else. For each:

1. Find the place on the default branch. Line numbers drift: search for the function or name it gives, with `git grep -n -w`.
2. Check it still holds. Drop a hint the code no longer shows, and say so in the proposal.
3. Group hints that point at one place or one cause. Several hints about one module are a stronger signal than any one of them.
4. Make each surviving hint a candidate for step 3. Read around it too: the smell a hint names is often a symptom of a bigger one nearby.

## 1. Signals: rank where tools point

They see one function at a time. Run a tool the project doesn't depend on with `uvx`, and add a pytest plugin for one run with `uv run --with`, so nothing is added to the project. Both download from PyPI. If a tool can't run, skip its signal and say so in the report.

| Signal | Command |
|---|---|
| Complex functions | `ruff check --select C901 --config 'lint.mccabe.max-complexity = 6' src`, which ranks below the project's own limit |
| Functions near the size limits | `ruff check --select PLR0911,PLR0912,PLR0913,PLR0915,PLR0917 src`, lowering the `lint.pylint.max-*` settings with `--config` if the project already passes |
| Often changed | `git log --format= --name-only --since=1.year -- '*.py' \| sort \| uniq -c \| sort -rn \| head -20`. Complex and often changed comes first. |
| Dead code | `uvx vulture src --min-confidence 60`, then `git grep -n -w <name>` for each public name, to find those used in one module or only by tests |
| Untested or unreachable branches | `uv run --with pytest-cov pytest --cov=src --cov-branch --cov-report=term-missing`; `mypy --warn-unreachable` |
| Duplicated code | `uvx pylint --disable=all --enable=duplicate-code src` |
| Import cycles | `uvx pylint --disable=all --enable=cyclic-import src` |
| Suppressed warnings | `git grep -nE '# (noqa\|type: ignore\|pragma: no cover\|pylint: disable)' src`, and every entry in `per-file-ignores` |
| Tests that work around the code | `git grep -nE 'mock\.patch\|monkeypatch\.setattr\|time\.sleep\|readouterr\(\)$' tests`: patching internals, sleeps, discarding output an earlier step left |

A suppression or a test workaround marks a place where the code fought someone. Each is a candidate, even in simple code.

## 2. Exploring: read flows and modules whole

This finds what no tool ranks: a value carried through layers, a check made twice, a concept split across modules, a thing with no honest name. Most structural findings come from here. Work through these in order, and write notes as you go; a finding often needs two of them to show.

1. **Trace each entry point end to end.** Pick each command, request handler or `main`, and follow it to its last effect, one call at a time. At each hop, note what is passed and what is done with it. Look for:
   - a value passed down unchanged through several calls;
   - a value converted and then converted back;
   - the same check, lookup or read made twice on one path;
   - a step whose result nothing on the path uses;
   - an effect, such as a write or a print, buried several calls below the entry point.
2. **Map the modules.** Write one sentence per module saying what it owns. A sentence that needs "and" is a module doing two jobs. Two sentences that claim the same thing are two modules owning one concept. A module with no honest sentence is a candidate to merge or delete.
3. **Map the concepts.** For each term in `GLOSSARY.md`, or each noun the code uses most, find where it lives in the code: `git grep -n -w <term> src`. One concept spread across several classes or dicts, or one class standing for two concepts, is a finding.
4. **Read the public surface.** For each module, list its names without a leading underscore. A name used only inside its module, a parameter every caller passes the same value, and an argument type wider than any caller needs all make the surface bigger than the job.
5. **Read the tests as a newcomer would.** For each test module, note what a test must set up before it can call the code. Setup that grows from file to file, fixtures that build half the system, and tests that check through private names show where the code is hard to use.
6. **Explain it.** For each flow and module, write the two or three sentences a newcomer would need. Where the explanation gets long, or needs "except when", the code is more complex than its job.

Everything you note is a candidate for step 3.

## 3. Read each candidate with the smell skills

For each candidate from steps 0, 1 and 2:

1. Read the whole function or class, at its definition and at every use: `git grep -n -w <name>`.
2. Ask `python-smells`' checklist, and read the reference each "yes" points to.
3. Check its names with `python-naming-smells`. **A name you can't make honest is a structure finding, not a rename.** It usually means the thing does two jobs or sits in the wrong module: take it to `python-smells` question 4 or 5.
4. Then ask the questions below, which matter when hunting through existing code more than when reviewing a diff.

### Questions for existing code

- **Is an `isinstance` ladder dispatching on types the project owns?** Consider `match`, `functools.singledispatch`, or a method on each type.
- **Does an object hold its own copy of a client, path or config** that another object owns? Pass the owner's instead.
- **How do well-known Python projects do this?** The standard library, pip, pytest, requests. Look it up rather than invent a pattern.
- **Could it come back?** If a ruff rule, a `[tool.ruff.lint.flake8-tidy-imports.banned-api]` entry or a test would stop it, propose that too. Check the rule on a small file first: ruff's rules have blind spots.

## 4. Sketch, then decide

For any finding beyond a rename, write the code as it would look after. A sketch often shows that a change only moves complexity around; drop those. Compare before and after: lines, branches, parameters, public names, and concepts a reader must hold.

Check each finding that adds code, such as a guard, a helper or a test, against `python-smells` questions 1, 2 and 10, as that skill asks.

Write a task for a finding only when all of these hold:

| Test | Holds when |
|---|---|
| It removes something | Something in the comparison went down, and nothing important went up. |
| It is worth a task | The gain is more than the cost of planning, doing and reviewing it. A rename of a private name used twice rarely is; a concept removed, a test workaround gone, or a function a newcomer can now follow usually is. |
| You are confident | You would defend the shape, not just try it. |
| Behaviour is kept | Callers and users see no difference. A behaviour change is allowed only when it is the point of the task, and the task says exactly what changes. |
| It reverses no decision | It goes against no ADR or design rule. Report one that does, with the reason, instead. |

Skip the rest. A finding that needs a choice only the human can make, such as a change to a command line, a public API or a dependency, still gets a task: put the choice under "Open questions", with your recommendation.

## 5. Write the tasks

Most valuable first, at most five per run; report the rest.

- **One concern per task.** Group small renames of one kind into one task. Give each restructure its own.
- Write each task to `<slug>/TASK.md` in the directory you were told, or in `refactoring-tasks/` beside the code checkout. The slug is a few words in kebab case. Leave the id as `<id>`: the human chooses it with `foundry task create`.
- Follow the task template's sections, in order. Write each for a planner and a dev who haven't seen your notes:

| Section | What to put there |
|---|---|
| `# Task <id>: <title>` | The change, in a few words: what goes away or what becomes simpler. |
| Goal | What is hard now, for a reader, a test or a change, and what the change removes. One paragraph. |
| Acceptance criteria | Checkable statements, each with an id (`AC1`, …), checkable from outside the code or by a search. Always: behaviour is unchanged, or exactly what changes; the existing tests pass, changed only where they reached into what was removed; the project's checks pass. Then what must be gone or true afterwards, such as "`move_notes` no longer exists" or "no test patches `_read_config`". |
| Out of scope | The neighbouring smells you saw and are leaving, each with an id (`OS1`, …), so the dev doesn't widen the task. |
| Risks | Where, as `path.py:line` and the function, class or flow, and how it was found: the hint, the signal from step 1, or the exploring step from step 2. The smell, by `python-smells` number and name or `python-naming-smells` smell. Your sketch, as a direction the dev's `PLAN.md` may improve on. Another task this one needs merged first, as an `After:` line under the title. |
| Terms | Glossary terms the change adds, renames or retires. Empty if none. A decision worth an ADR goes to the architect, as a question in your report. |
| Open questions | Choices only the human can make, each with the options and your recommendation. Empty otherwise. |

After a restructure you've written up, explore the flow again as it would look after. The change often shows the next simplification, or a new thing that is hard to name. Write that as a second task that depends on the first.

## 6. Report

End the run with a short report:

- the tasks you wrote, one line each, in the order to do them, saying which depend on others;
- the findings you skipped, one line each, with the test from step 4 that failed;
- the signals you couldn't run, and why;
- when you were given hints, the ones you dropped and why.

## Don't

- Don't change the code. Your output is tasks and a report.
- Don't sketch a class, base class or `Protocol` to remove two similar lines.
- Don't sketch a `noqa`, a `type: ignore` or a test workaround into a change. If one seems needed, the shape is wrong.
- Don't write a task because code is old or unfamiliar. Each task needs a concrete cost.
- Don't widen a task beyond its finding. Name the neighbours under "Out of scope" instead.
