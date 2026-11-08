---
name: python-refactoring-opportunities
description: Hunt a Python codebase for refactors that make it simpler, and open a PR for each one worth it, on its own or from given hints such as follow-ups. Use when asked to find refactors or simplify.
---

# Finding refactoring opportunities in Python

Find changes across a Python codebase that make it simpler to read, test and change, and make the worthwhile ones as pull requests. Nobody checks in with you along the way: you decide what is worth a PR, and the human accepts or closes each one. A change counts only if it removes something: lines, branches, parameters, concepts, or a workaround in a test. Opening no PR is a good result when nothing clears the bar.

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

Run tools the project doesn't depend on with `uvx`, so nothing is added to it. They see one function at a time.

| Signal | Command |
|---|---|
| Complex functions | `uvx radon cc -s -n C src` (grade C or worse), and `ruff check --select C901 --config 'lint.mccabe.max-complexity = 6' src` to rank below the project's own limit |
| Functions near the size limits | `ruff check --select PLR0911,PLR0912,PLR0913,PLR0915,PLR0917 src`, lowering the `lint.pylint.max-*` settings with `--config` if the project already passes |
| Often changed | `git log --format= --name-only --since=1.year -- '*.py' \| sort \| uniq -c \| sort -rn \| head -20`. Complex and often changed comes first. |
| Dead code | `uvx vulture src --min-confidence 60`, then `git grep -n -w <name>` for each public name, to find those used in one module or only by tests |
| Untested or unreachable branches | `pytest --cov=src --cov-branch --cov-report=term-missing`; `mypy --warn-unreachable` |
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

Open a PR for a finding only when all of these hold:

| Test | Holds when |
|---|---|
| It removes something | Something in the comparison went down, and nothing important went up. |
| It is worth a review | The gain is more than the reviewer's time. A rename of a private name used twice rarely is; a concept removed, a test workaround gone, or a function a newcomer can now follow usually is. |
| You are confident | You would defend the shape, not just try it. |
| Behaviour is kept | Callers and users see no difference. A behaviour change is allowed only when it is the point of the PR, and the description says exactly what changes. |
| It stands alone | It doesn't need another finding merged first. If it does, stack it on that PR's branch and say so. |
| It doesn't reverse a decision | It goes against no ADR or design rule. Report one that does, with the reason, instead. |

Skip the rest. When a finding needs a choice only the human can make, such as a change to a command line, a public API or a dependency, report it instead of guessing.

## 5. Make the PRs

Most valuable first, at most five per run, so the human can review them; report the rest.

- **One concern per PR.** Batch small renames of one kind into one PR. Give each restructure its own.
- Branch from the default branch, fresh for each PR, unless it is stacked.
- Follow the project's own rules for commits, tests and docs. Change no test only to make it pass. Update the docs, glossary terms or ADRs the change makes wrong.
- Run all the project's checks. Never open a PR whose checks fail.
- Write the description so the human can accept or close it without asking you anything:

| Field | Content |
|---|---|
| Where | `path.py:line`, and the function, class or flow |
| Found by | the hint it came from, the signal from step 1, or the exploring step from step 2 |
| Smell | the `python-smells` number and name, the `python-naming-smells` smell, or the question from this skill |
| Cost before | what was hard for a reader, a test or a change, in one or two sentences |
| Removes | what went away, with the before and after counts that matter |
| Behaviour change | none, or exactly what a user or caller now sees, such as output moving from stdout to stderr |
| Alternatives | the other shapes or names you weighed, and why this one |

After a restructure, explore the changed flow again before the next PR. The new code often shows the next simplification, or a new thing that is hard to name.

## 6. Report

End the run with a short report:

- the PRs you opened, one line each, in the order to review them, saying which are stacked;
- the findings you skipped, one line each, with the test from step 4 that failed;
- the choices only the human can make, each with your recommendation;
- when you were given hints, the ones you dropped and why.

## Don't

- Don't add a class, base class or `Protocol` to remove two similar lines.
- Don't write a workaround in a test, such as subclassing `list` or patching a private function. A test that needs one is a finding about the code. Use pytest's fixtures: `caplog`, `capsys`, `tmp_path`, `monkeypatch.setenv`.
- Don't add a `noqa` or `type: ignore` to land a refactor. If one seems needed, the shape is wrong.
- Don't propose a change because code is old or unfamiliar. Each finding needs a concrete cost.
- Don't reformat or rename beyond the finding; it hides the change that matters.
