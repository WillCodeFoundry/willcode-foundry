# Task wcf-0033: foundry task create picks the next task id when TASK is left out

## Goal
`foundry task create PROJECT` without TASK creates the project's next task, so you no longer look up the
highest id by hand. The next id keeps the prefix the project's tasks already use, and takes one more than
the highest number taken, with at least four digits. An id is taken if it is an open task, a closed task,
or has a task branch, even with no notes. When no single prefix can be followed, create refuses and
creates nothing. Giving TASK works exactly as it does today.

## Acceptance criteria
- [ ] AC1: On a project whose tasks are `wcf-0030` (open) and `wcf-0032` (closed), plus a branch
  `task/wcf-0033` with no notes, `foundry task create PROJECT` exits 0 and prints
  `created task wcf-0034 in PROJECT` then `run it with: foundry run PROJECT wcf-0034`. Afterwards the
  repository has branch `task/wcf-0034` and `.agent/tasks/open/wcf-0034/` on `agent-notes`, the same as
  `foundry task create PROJECT wcf-0034` would leave.
- [ ] AC2: The highest taken number counts whichever kind holds it. With the highest at `wcf-0007`, the
  created task is `wcf-0008` whether `wcf-0007` is open, closed, or only a branch.
- [ ] AC3: The number is padded to four digits and grows past four: `wcf-0041` → `wcf-0042`,
  `wcf-9999` → `wcf-10000`, `wcf-00041` → `wcf-0042`.
- [ ] AC4: Names that aren't valid task ids are ignored, as prefixes and as numbers. On a project with
  `wcf-0005` and branches `task/spike` and `task/WCF-0099`, the created task is `wcf-0006`.
- [ ] AC5: On a project with no task id taken (no task branches and no task notes), it exits 1. stderr
  says to give TASK, and the repository's branches are unchanged: no new task branch, no `agent-notes`.
- [ ] AC6: On a project whose taken ids use more than one prefix (e.g. branch-only `abc-0001` and closed
  `wcf-0002`), it exits 1. stderr names every prefix in alphabetical order and says to give TASK, and the
  repository's branches are unchanged.
- [ ] AC7: When two creates without TASK pick the same id, and the first pushes before the second, the
  second exits 1 with an `error:` line on stderr. The repository then holds only the first's task branch,
  notes dir and commit, with nothing from the second. It does not retry with another id.
- [ ] AC8: `foundry task create PROJECT TASK` behaves as before, including on a project with no tasks or
  with mixed prefixes. The existing tests of create with TASK pass unchanged.
- [ ] AC9: The README command table shows `foundry task create PROJECT [TASK]` and says the next task id is
  picked when TASK is left out. The README line describing a task id's form names its prefix and number.
  `tests/test_docs.py` passes.
- [ ] AC10: `foundry task create --help` shows TASK as optional and says what is picked when it is left out.
- [ ] AC11: ruff and the host tier pass, as CONTRIBUTING.md runs them.

## Out of scope
- OS1: Setting a project's prefix in `config/foundry.yaml`.
- OS2: Choosing the prefix any other way, such as from the project's name, or for a project's first task.
- OS3: Reusing gaps in the numbering: `wcf-0001` and `wcf-0005` give `wcf-0006`, never `wcf-0002`.
- OS4: A command or option that only prints the next id.
- OS5: Retrying with the next id after losing a race, or a friendlier message than git's push rejection.
- OS6: Leaving TASK out of `close`, `reopen`, `handoff` or `run`.

## Risks
- A race's refusal shows git's push rejection, not "already exists". This matches two creates of the
  same explicit id today (AC7, OS5).
- An id whose branch was deleted and whose notes never existed counts as free again, and may be reused.
- No existing follow-up touches this code.

## Terms
- **Task id** (sharpened): a task's name, made of a prefix of lowercase ASCII letters, `-`, then a
  number of four or more digits, such as `wcf-0042`. foundry never changes its case.

## Open questions
