# Task wcf-0034: Show what one task is waiting for

## Goal
`foundry task list` says whose turn each task is, but not what the task needs.
Today you find that out by opening its `LOG.md` on `agent-notes` by hand. Add
`foundry task show PROJECT TASK`, which prints one task's turn and the last
entry of its `LOG.md`. That entry is where a role that hands the task to you
puts its questions. This replaces wcf-0030, a larger version that was closed.

## Acceptance criteria
- [ ] AC1: For an open task, `foundry task show PROJECT TASK` prints on stdout
      the line `turn: <TURN>`, the stripped text of its `TURN`, then one blank
      line, then the last entry of its `LOG.md`. It prints nothing on stderr
      and exits 0. The last entry runs from the last line that starts with
      `## `, one or more digits and ` · `, to the end of the file. It is
      printed as written, except that blank lines and spaces at the end of the
      file are dropped, so the output ends with one newline.
- [ ] AC2: For a closed task, it prints the same, after a first line
      `status: closed`. An open task has no status line.
- [ ] AC3: For a `LOG.md` with no such heading line, such as one holding only
      the template's `# Log`, the entry is replaced by the line
      `no log entry yet`. It exits 0.
- [ ] AC4: An unknown project, or a task id that isn't valid, is refused with
      the message `foundry task create` gives for it, before any git command
      runs.
- [ ] AC5: Each failure prints `error: <message>` on stderr, prints nothing on
      stdout, and exits 1:
      - the repository can't be reached;
      - it has no `agent-notes` branch;
      - the task is neither open nor closed, or is both, with the messages
        `foundry run` gives;
      - the task is malformed: its `TURN` or `LOG.md` is missing, not a file,
        or a symlink, or its `TURN` is empty. The message names the task and
        that file;
      - the failures in AC4.
- [ ] AC6: Showing only reads. It fetches `agent-notes` exactly once, as
      counted by the test suite's counting stand-in for git. It makes no
      commit and no push, leaves every remote branch as it was, and works
      with no signing key configured.
- [ ] AC7: A `TURN` or `LOG.md` that is a symlink is never followed: `show`
      fails as AC5 says, and prints nothing of the file it points to.
- [ ] AC8: `foundry task --help` lists `show`. The README's command table lists
      `foundry task show PROJECT TASK`. The README sentence saying a task
      waiting for you has "the question at the end of its `LOG.md`" names
      `foundry task show`. `tests/test_docs.py` passes.
- [ ] AC9: The project's checks in CONTRIBUTING.md pass.

## Out of scope
- OS1: Picking out questions or answers from the log.
- OS2: Any part of the log before its last entry.
- OS3: `REVIEW.md`.
- OS4: The task's pull request and its CI state.
- OS5: Machine-readable output.
- OS6: Any change to what `foundry task list` does.
- OS7: Old tasks with only a `PROGRESS.md`: they fail as malformed (AC5).
- OS8: Colour or paging.
- OS9: Showing several tasks in one run.

## Risks
- wcf-0034 and wcf-0033 (open) both change `foundry task` and the README's
  command table, so whichever merges second may conflict.
- A line inside an entry that looks like a heading, such as one in a code
  block, starts the "last entry" there. Accepted.
- No follow-ups are recorded against the code this touches.

## Terms
- None.

## Open questions
- None.
