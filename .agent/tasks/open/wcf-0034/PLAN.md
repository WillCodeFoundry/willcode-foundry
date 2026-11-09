# Plan: wcf-0034

## Approach
`ProjectTasks` gains one read: `fetch_task_turn_and_log`, which fetches `agent-notes` once and reads the task's
status, its `TURN` and its `LOG.md` from that one fetch, as `fetch_task_turn` does for the turn alone. It refuses a
`TURN` or `LOG.md` that is a link before reading it. A pure function `last_log_entry` cuts the last entry out of the
log text, beside `log_with_handoff_entry` and sharing its `_LOG_HEADING`. The command `show` is a composition root
in `commands/task.py`; a pure `show_lines` turns the read into the lines it prints. Because: DR7.

Links: `FetchedBranch.read_text` reads a link as its target's name, and `task list` relies on that (OS6), so it
stays. `FetchedBranch` gains `is_link(path)`, read from the mode `git ls-tree` already prints. Turned down: a
second `read_text` that refuses links, which would duplicate the entry check; and a flag on `read_text`, which
ruff's boolean-flag rule bans.

The task id is checked with `Task.as_open` before the scratch clone is made, as `handoff_main` does, so a bad id
runs no git (AC4). An unknown project already fails in `config.project`, before any git.

Every failure is a `FoundryError` or `GitError` raised by existing code or the one new check; `cli.main` already
prints them as `error: <message>` and exits 1 (AC5). Because: DR6.

## Steps
1. Refactor, no behaviour change: move the counting stand-in for git out of
   `test_listing_costs_one_fetch_however_many_tasks` into `tests/support/machine.py`, beside its siblings, as
   `counting_stand_in(directory, name) -> Path`: a command in `directory` that records each run's arguments, one
   line each, then runs the real `name`, found on `PATH` when it is made. It returns the file of recorded calls,
   its one return shape; the caller puts `directory` first on `PATH`, as for `scripted_stand_in`. Add
   `fetch_count(git_calls) -> int` to `tests/support/project_repository.py`, the git fetches that file records.
   Move the `no_signing_key` fixture from `tests/test_project_tasks.py` to `tests/conftest.py`, so the end-to-end
   AC6 test can use it. The existing tests use all three. Amended: R3, R6, R7. Because: one shape serves both the
   env a `ProjectTasks` takes and `process_environment.prepend_to_path`; the family word is `stand_in`; `log` is
   the glossary's Log.
2. `FetchedBranch.is_link`, with `_ls_tree` returning each entry's mode too. Tests in
   `tests/test_project_scratch_clone.py`.
3. `last_log_entry`, `TaskTurnAndLog` and `ProjectTasks.fetch_task_turn_and_log`, test-first in
   `tests/test_project_tasks.py`.
4. `show` in `commands/task.py`: the parser, `show_main`, `show_lines`; test-first in `tests/test_task_command.py`.
5. Docs, below.

## Names
- `foundry task show PROJECT TASK`: from `TASK.md`.
- `FetchedBranch.is_link(path) -> bool`: "link" is the word `ProjectScratchClone.write` and its message already use.
- `ProjectTasks.fetch_task_turn_and_log(task_id) -> TaskTurnAndLog`: `fetch_` as for `fetch_task_turn`, which
  also fetches `agent-notes` and reads from it.
- `TaskTurnAndLog(task, turn, log)`: a frozen dataclass beside `TaskTurn`, which has `task` and `turn`; `log` is the
  glossary's **Log**, the whole text of `LOG.md`.
- `last_log_entry(log) -> str | None`: the last entry, or None when the log has none. "entry" is the glossary's word.
- `show_main`, `show_lines(turn_and_log) -> list[str]`: as `handoff_main` and `handoff_lines`.
- Tests only: `counting_stand_in(directory, name) -> Path`, in the family of `scripted_stand_in`, `stand_in` and
  `recording_stand_in`; "counting" is TASK.md's word. `fetch_count(git_calls) -> int`: `git_calls` names what the
  file holds, git's calls, and keeps "log" for `LOG.md`. Amended: R6, R7. Because: R6, R7.

## Errors
New:
- A link: `task tst-0000's TURN is a link, and foundry reads only files: agent-notes has a link at
  .agent/tasks/open/tst-0000/TURN` (and the same with `LOG.md`).

Reused, word for word as the code gives them today:
- Unknown project: `unknown project 'nope'; known: …` (`config.project`).
- Invalid id: `task id 'x' is not valid: use lowercase letters, '-', then four or more digits (e.g. wcf-0042)`.
- Unreachable repository: git's `GitError`, `git -C … ls-remote --heads origin failed: …`.
- No `agent-notes`: `the project repository has no agent-notes branch`.
- Neither open nor closed: `task tst-0001 doesn't exist: agent-notes has neither .agent/tasks/open/tst-0001/ nor
  .agent/tasks/closed/tst-0001/`; both: `task tst-0001 is both open and closed: agent-notes has … and …/`. These
  are `foundry run`'s, as both go through `_read_task`.
- `TURN` missing, a dir or blank: `task tst-0000 has no turn: agent-notes has no .agent/tasks/open/tst-0000/TURN,
  or it is empty.` (`MissingTurnError`).
- `LOG.md` missing or a dir: `task tst-0000 has no LOG.md: agent-notes has no file
  .agent/tasks/open/tst-0000/LOG.md` (`_read_log`).

Printed on stdout: `status: closed`, `turn: <TURN>`, a blank line, then the entry or `no log entry yet`.

## Tests
- AC1: `test_project_tasks.py`: `last_log_entry`, parametrized over a log whose last heading is followed by
  blank lines and blank lines inside the entry; trailing blank lines and spaces; a multi-digit number; a
  `## 3 · ` not at the start of a line and a `## x · ` heading, which don't count; the entry ends without a
  newline. `fetch_task_turn_and_log` returns the task, its stripped turn and its log text. `test_task_command.py`:
  `show_lines` for an open task; and end to end through `cli.main` with `enter_foundry` and `project_repository`,
  stdout exactly `turn: dev\n\n## 2 · dev · progress\n…\n`, stderr empty, exit 0.
- AC2: `show_lines` for a closed task starts with `status: closed`; end to end on `cls-0000`.
- AC3: `last_log_entry("# Log\n")` is None; `show_lines` gives `no log entry yet`; end to end, exit 0.
- AC4: end to end with `counting_stand_in(dir, "git")` and `dir` prepended to `PATH`
  (`process_environment.prepend_to_path`): an unknown project and an invalid id each print the message above and
  leave the calls file absent or empty. The AC6 test below shows the same setup records git when it runs.
  Amended: R1, R3. Because: an empty record proves nothing unless the setup is shown to record.
- AC5: `test_project_tasks.py`, parametrized: each malformed case (TURN missing, a dir, blank, a link; LOG.md
  missing, a dir, a link; via `edit_notes`) raises its message. End to end, parametrized over every AC5 failure,
  including an unreachable repository and a bare one with no `agent-notes`: stdout empty, stderr one
  `error: <message>` line, exit 1.
- AC6: end to end through `cli.main`, in `test_task_command.py`, with the `no_signing_key` fixture and the same
  `counting_stand_in` setup as AC4: a successful `foundry task show` exits 0, `fetch_count(git_calls) == 1`, no
  recorded call is a `commit` or a `push`, and `git for-each-ref` on the project repository is the same before
  and after. So a `show_main` that fetched again fails it. Amended: R1. Because: counted at `ProjectTasks` only, a
  second fetch in `show_main` would pass.
- AC7: `TURN` linked to `/etc/hostname`, and `LOG.md` linked to a notes file holding a marker line: end to end,
  neither the marker nor the target's text appears on stdout or stderr, and the failure is AC5's. `is_link` in
  `test_project_scratch_clone.py`: a link is one, and a file, a dir and a missing path are not.
- AC8: `test_task_command.py`: `foundry task --help` names `show`. `tests/test_docs.py` checks the README's command
  table against the parser, and a new test there checks that the README sentence holding "the question at the end
  of its `LOG.md`" also names `foundry task show`. Amended: R2. Because: the table test reads table rows only.
- AC9: the checks in CONTRIBUTING.md, run before each push.

## Docs
- README: a `foundry task show PROJECT TASK` row in the command table; the sentence about "the question at the end of
  its `LOG.md`" names `foundry task show`.
- ARCHITECTURE.md's codemap row for `project_tasks.py`: add showing a task's turn and last log entry.
- The module docstrings of `commands/task.py` and `project_tasks.py`, and the `task` parser's help, which list the
  actions.
- `FetchedBranch.read_text`'s docstring points to `is_link`.
- CONTRIBUTING.md's helper table: `counting_stand_in` in the stand-ins' row, and `fetch_count`. Amended: R6.
  Because: R6.
- `_ls_tree`'s docstring: it gives each entry's mode too. Amended: R4. Because: R4.
- `tests/support/project_repository.py`'s module docstring: it also counts git's fetches. Amended: R5.
  Because: R5.
