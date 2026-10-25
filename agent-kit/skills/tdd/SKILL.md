---
name: tdd
description: Test-driven development. Use when the dev or qa role builds a feature or fixes a bug test-first, at the seams TASK.md names, or works with red-green-refactor or integration tests.
metadata:
  source:
    repo: mattpocock/skills
    path: skills/engineering/tdd
    commit: 5beb35b040e3de97e54fa9e386d7e42d15c295c2
    author: Matt Pocock
    license: MIT (see ../LICENSE-mattpocock)
  adapted: for willcode-foundry, edited in place; see Skills in its README
---

# Test-Driven Development

TDD is the red → green loop. This skill is the reference that makes that loop produce tests worth keeping: what a good test is, where tests go, the anti-patterns, and the rules of the loop. Every section applies on every cycle: consult them before and during the loop, not after.

When exploring the codebase, read `GLOSSARY.md` (if it exists) so test names and interface vocabulary match the project's domain language, and respect ADRs in the area you're touching.

## What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't. A good test reads like a specification: "user can checkout with valid cart" tells you exactly what capability exists, and it survives refactors because it doesn't care about internal structure.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Seams: where tests go

A **seam** is the public boundary you test at: the interface where you observe behavior without reaching inside. Tests live at seams, never against internals.

**Test only at pre-agreed seams.** The seams are agreed when the task is planned: they are under "Seams to test" in the task's `TASK.md`, each with what it catches. No test is written at a seam that isn't there. You can't test everything, so agreeing the seams up front is how testing effort lands on the critical paths and complex logic instead of every edge case.

If "Seams to test" names none, pick them yourself. Ask: "What's the public interface, and which seams should we test?" Give each seam a one-line note on what it catches and what it misses, and write them under "In progress" in `PROGRESS.md` before writing any test. Then continue; there is no one to confirm them with.

When the shape of that interface is itself in question (how deep the module is, where the seam belongs, what the interface should expose), call the Skill tool with "codebase-design" for the vocabulary. It is the shared source of the module, interface, depth, seam, adapter, leverage and locality terms, and it is a reference to consult, not a session to run.

## Anti-patterns

- **Implementation-coupled**: mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`, a snapshot derived by hand the same way, a constant asserted equal to itself), so it passes by construction and can never disagree with the code. Expected values must come from an independent source of truth: a known-good literal, a worked example, the spec.
- **Horizontal slicing**: writing all tests first, then all implementation. Bulk tests verify _imagined_ behavior: you test the _shape_ of things rather than user-facing behavior, the tests go insensitive to real changes, and you commit to test structure before understanding the implementation. Work in **vertical slices** instead: one test → one implementation → repeat, each test a **tracer bullet** that responds to what the last cycle taught you.

## Rules of the loop

- **Red before green.** Write the failing test first, then only enough code to pass it. Don't anticipate future tests or add speculative features.
- **One slice at a time.** One seam, one test, one minimal implementation per cycle.
- **Refactoring is not part of the loop.** The reviewer role reviews the change, with the `code-review` skill, and its findings come back to you through `REVIEW.md`. Don't widen the task to tidy up what you pass: note it under "Next" in `PROGRESS.md` instead.
- **Each green slice is a commit.** Once a slice's test and the project's checks pass, commit it on the task branch with a message that says why, then update `PROGRESS.md` and commit it on `$AGENT_NOTES_BRANCH`, as "Work in small steps" in `AGENTS.md` says.
