# Task release checklist

A task is ready only when every line holds.

- [ ] The goal says why, not only what.
- [ ] Every acceptance criterion has an id (`AC1`, `AC2`, …) and can be checked from outside the code without a judgement call.
- [ ] No criterion merely restates the goal.
- [ ] No criterion or out-of-scope line says how to build it: no function, file or module to change, and no code to copy. That is the dev's `PLAN.md`.
- [ ] Performance, compatibility and security were considered; any that apply
      appear as criteria.
- [ ] "Out of scope" has at least one entry, each with an id (`OS1`, …), each a behaviour or a user.
- [ ] Every follow-up on the code the task touches is taken in as a criterion, put out of scope, or listed under "Risks".
- [ ] No risk says how the code will behave: a behaviour the task needs is a criterion.
- [ ] Every term under "Terms" is checked against `GLOSSARY.md`.
- [ ] "Open questions" is empty.
- [ ] No `<placeholder>` text from the template remains.
- [ ] A dev could write a plan without asking anything.
- [ ] The task is one task: one session's work, one vertical slice that can merge on its own, no
      hidden second task. A slice that needs another merged first has an `After:` line.
