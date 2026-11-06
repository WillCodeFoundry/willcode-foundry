---
name: python-smells
description: 'Judgement-call smells that linters miss: building for nobody, distrusting your own types, hiding failure, rules in the wrong place, functions that do two jobs, copying instead of finding the seam, growth by accretion, narrating comments, hidden costs, tests that prove nothing, and rewrites that only satisfy a checker. Use when the dev writes or changes Python code, before each commit, and when the reviewer reads a diff for smells.'
---

# Python smells

Check each function, class and test your diff adds or changes against the questions below. Passing ruff and mypy says little here: these smells are judgement calls, and linters rarely flag them.

The project's `AGENTS.md` and the design rules in `ARCHITECTURE.md` win where they say otherwise.

## How to use it

1. List every function, class and test the diff adds or changes.
2. Read each one whole, at its uses as well as its definition.
3. Ask each question in the checklist. A "yes" points to a file in `references/`.
4. Compare your code with that smell's bad example, and check its "Fine when" line before changing anything.
5. Fix what you can locally. A fix that needs a new interface or module is a design question, as the `code-review` skill says.

Read a reference file only when a question points to it. Its examples are invented, so match the shape, not the names.

## Checklist

| # | Ask | Read |
|---|---|---|
| 1 | Does every new function, parameter, branch and case have a caller or a requirement today? | [Building for nobody](references/building-for-nobody.md) |
| 2 | Do I re-check, widen or cast what a type already guarantees? | [Distrusting your own types](references/distrusting-types.md) |
| 3 | When something is wrong, does the code repair it, swallow it, fake a value, misreport it, or leave the caller guessing? | [Hiding failure](references/hiding-failure.md) |
| 4 | Is each rule enforced in one place, where its state lives, on every path, and on the value actually used? | [Rules in the wrong place](references/rules-in-the-wrong-place.md) |
| 5 | Does each function do one job that its name and signature say? | [Functions that do two jobs](references/functions-that-do-two-jobs.md) |
| 6 | Did I copy or rebuild something that exists, or go around a helper, a name or a parser made for this? | [Copying instead of finding the seam](references/copying-instead-of-the-seam.md) |
| 7 | Did I add one more branch, flag or case to code that every change already edits? | [Growing by accretion](references/growing-by-accretion.md) |
| 8 | Does a comment or docstring repeat the code, describe callers or history, or promise what the code doesn't do? | [Narrating instead of naming](references/narrating-instead-of-naming.md) |
| 9 | Does anything rebuild a constant per call, or block an event loop? | [Hidden costs](references/hidden-costs.md) |
| 10 | Would each new test fail if the behaviour it names broke? | [Tests that prove nothing](references/tests-that-prove-nothing.md) |
| 11 | Did I reshape clear code only to satisfy a checker, a budget or a reviewer's request? | [Obeying the letter of a rule](references/obeying-the-letter.md) |

## Review requests

Hold a reviewer's request for more guards, fallbacks, helpers or tests to the same bar as your own code. Check it against questions 1, 2 and 10 before adding it, and answer the review instead when it fails them.
