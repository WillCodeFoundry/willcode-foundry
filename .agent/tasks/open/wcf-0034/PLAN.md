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
   `test_listing_costs_one_fetch_however_many_tasks` into `tests/support/project_repository.py` as
   `counting_git(directory, git_env)`, returning the env with it first on `PATH` and its call log; and
   `fetch_count(log)`. The existing test uses them. Add it to CONTRIBUTING.md's helper table.
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
- AC4: end to end with `counting_git`'s dir prepended to `PATH` (`process_environment.prepend_to_path`): an
  unknown project and an invalid id each print the message above and leave the call log empty.
- AC5: `test_project_tasks.py`, parametrized: each malformed case (TURN missing, a dir, blank, a link; LOG.md
  missing, a dir, a link; via `edit_notes`) raises its message. End to end, parametrized over every AC5 failure,
  including an unreachable repository and a bare one with no `agent-notes`: stdout empty, stderr one
  `error: <message>` line, exit 1.
- AC6: `test_project_tasks.py`, with the `no_signing_key` fixture and `counting_git`: `fetch_count(log) == 1`, no
  `commit` or `push` in the log, and `git for-each-ref` on the repository the same before and after.
- AC7: `TURN` linked to `/etc/hostname`, and `LOG.md` linked to a notes file holding a marker line: end to end,
  neither the marker nor the target's text appears on stdout or stderr, and the failure is AC5's. `is_link` in
  `test_project_scratch_clone.py`: a link is one, and a file, a dir and a missing path are not.
- AC8: `test_task_command.py`: `foundry task --help` names `show`. `tests/test_docs.py` checks the README's command
  table against the parser.
- AC9: the checks in CONTRIBUTING.md, run before each push.

## Docs
- README: a `foundry task show PROJECT TASK` row in the command table; the sentence about "the question at the end of
  its `LOG.md`" names `foundry task show`.
- ARCHITECTURE.md's codemap row for `project_tasks.py`: add showing a task's turn and last log entry.
- The module docstrings of `commands/task.py` and `project_tasks.py`, and the `task` parser's help, which list the
  actions.
- `FetchedBranch.read_text`'s docstring points to `is_link`.
- CONTRIBUTING.md's helper table: `counting_git` and `fetch_count`.
