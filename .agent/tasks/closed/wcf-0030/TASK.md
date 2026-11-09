# Task wcf-0030: Show a task's turn and the questions nobody has answered

## Goal
`foundry task list` says which tasks wait for you, but not what each needs
from you. Today you find that out by reading the task's `LOG.md` by hand. Add
`foundry task show PROJECT TASK`, which prints one task's turn and the
questions in its `LOG.md` that no entry has answered yet, those asked of you
first. Unanswered questions are what block a task, so they are the part of the
log you most need to see.

## Acceptance criteria
- [ ] `foundry task show PROJECT TASK` prints on stdout, for an open task:
      a line `turn: <TURN>`, the stripped text of its `TURN`; then
      `open questions:`, followed by one line per open question, indented two
      spaces, as `<id> → <target> (entry <n>): <text>`; or, when none is open,
      the single line `open questions: none`. It exits 0.
- [ ] For a closed task (under `.agent/tasks/closed/`) it prints the same,
      with a first line `status: closed`. An open task has no status line.
- [ ] A question is a line that starts with `Asks <id> → <target>:`, after
      optional leading spaces and an optional `- `. Its text is the rest of
      that line, joined with single spaces to the indented lines straight
      after it (up to the first blank or unindented line), stripped. Only the
      `→` arrow counts; `->` does not.
- [ ] An answer is a line that starts with `Answers <id>:`, after optional
      leading spaces and an optional `- `. A mention of an id anywhere else in
      a line answers nothing.
- [ ] A question is open when no answer with its id comes after it in the
      log. One answer is enough, whoever wrote it. An answer whose id was never
      asked, such as one for a `REVIEW.md` finding, is ignored. Each `Asks`
      line is its own question: an id asked again after its answer is open
      again.
- [ ] `<n>` is the number in the nearest `## <n> · …` entry heading above the
      question. A question above any heading is printed without
      ` (entry <n>)`.
- [ ] Questions whose target is exactly `human` come first, then the rest,
      each group in log order.
- [ ] An unknown project is refused before anything is read, with the same
      message as `foundry task create` gives, and exit 1. A task id that isn't
      valid is refused as `create` refuses it.
- [ ] Each failure prints `error: <message>` on stderr, prints nothing on
      stdout, and exits 1: the repository can't be reached; it has no
      `agent-notes` branch; the task is neither open nor closed, or both (the
      messages `get_task_by_id` gives); its `TURN` is missing, empty or not a
      file (the message `read_task_turn` gives); its `LOG.md` is missing or
      not a file, with a message that names the task and the file.
- [ ] Showing reads only: it makes no commit and no push, needs no signing
      key, and costs one fetch of `agent-notes`.
- [ ] Finding the task and reading `TURN` and `LOG.md` go through git objects
      on the fetched `agent-notes` (`fetched_list_dir`, `fetched_read`), never
      a checkout or the checked-out files: a `LOG.md` that is a symlink reads
      as the link's target name, so it shows no questions.
- [ ] `LOG.md` is spelled once on foundry's side, in `src/foundry/task.py`, and
      a test holds it equal to `LOG_FILE` in `src/agent_runtime/git_hooks.py`.
- [ ] The README's command table lists `foundry task show PROJECT TASK`, so
      `tests/test_docs.py` passes. The README paragraph on `TURN` mentions
      `show`. `ARCHITECTURE.md`'s codemap describes where the log is read.
- [ ] The host tier, ruff and mypy pass.

## Out of scope
- The task's pull request and its CI state: the next task.
- A column in `task list` for open questions.
- How long a task has waited.
- Machine-readable output (`--json`).
- Changing `TURN`, answering a question, or starting a sandbox.
- Questions in `REVIEW.md`, or anything in `LOG.md` other than `Asks` and
  `Answers` lines; entries in a `PROGRESS.md`.
- Changing `get_task_by_id`, `read_task_turn` or `list_open_task_summaries`'
  behaviour; add beside them.
- wcf-0028's follow-ups: keeping `.agent/tasks/open/` with a `.gitkeep`;
  `foundry repo check` printing errors on stderr; `_require_command`; R4, a
  multi-line `TURN`.

## Context
- `src/foundry/commands/task.py`: add `show` beside `create`, `close`,
  `reopen` and `list`, taking the shared `task_arguments`. Update the `task`
  help text and the module docstring. Its `main` is a composition root that
  only builds and passes (design rule 7 in `ARCHITECTURE.md`). The printed
  lines come from a pure function the tests call, as `listing_lines` is for
  `list`.
- Errors: raise `FoundryError` and let `cli.main` print it as
  `error: <message>` and exit 1 (design rule 6). Unlike `list`, there is one
  task, so nothing carries on after a failure.
- `src/foundry/project_tasks.py`: `get_task_by_id` checks out `agent-notes`
  through `ProjectClone.check_out`, so `show` can't use it as it stands.
  `list_open_task_summaries` and `_read_fetched_turn` show the read path to
  follow: `fetch_branch` once, then `fetched_list_dir` / `fetched_read`, with
  `NotOnBranchError` for what is missing.
- `src/foundry/project_clone.py`: `fetch_branch`, `fetched_list_dir`,
  `fetched_read`, `NotOnBranchError`.
- `src/foundry/task.py`: the one place a task's names are spelled (design rule
  1): `NOTES_BRANCH`, `OPEN_DIR`, `CLOSED_DIR`, `TURN_FILE`, `HUMAN`,
  `Task.task_notes_dir`, `Task.turn_file`. `LOG.md` is spelled today only as
  `LOG_FILE` in `src/agent_runtime/git_hooks.py`, which foundry may not import
  (design rule 2, `tests/test_runtime_boundary.py`).
  `tests/test_task_contract.py` is where task names are held to other copies.
- The LOG.md format: `agent-kit/AGENTS.md` ("`LOG.md`"), GLOSSARY.md ("Log")
  and `docs/adr/0013-roles-talk-through-a-log.md`. Real logs on `agent-notes`
  (e.g. `.agent/tasks/open/wcf-0028/LOG.md`) have questions spanning several
  indented lines, reviewer questions by finding id (`Asks R16 → human`), and
  answers to findings never asked in the log (`Answers R16: fixed in …`).
- `config.Config.project` raises the unknown-project error `create` gives.
- `tests/test_task.py`: real repositories in temporary folders (`origin_dir`,
  `git_env`), a counting stand-in for git on `PATH`
  (`test_listing_costs_one_fetch_however_many_tasks`), and an end-to-end
  `cli.main` run. Tests never patch (design rule 3).
- No new dependencies.

## Seams to test
- The function that finds a log's open questions, called with plain text:
  multi-line questions, answers after and before a question, answers by id
  with no question, mentions of an id outside an `Answers` line, `->`, an id
  asked again, a question above any heading, the human-first order. Catches
  parsing and ordering bugs without git.
- The function that turns a task's status, turn and open questions into
  stdout lines, called with plain values: the status line, the none line,
  the question lines. Catches formatting bugs.
- The `ProjectTasks` method that reads one task for `show`, against a real
  repository in a temporary folder: an open and a closed task; each failure
  (not found, both open and closed, missing or empty `TURN`, missing
  `LOG.md`, no `agent-notes`, an unreachable repository); a symlinked
  `LOG.md`. Catches reading the wrong dir or branch, a checkout, and following
  links.
- The fetch count, with the counting stand-in for git. Catches a second fetch.
- The parser: `task show` takes a project and a task, as
  `test_create_takes_a_project_and_a_task` checks `create`.
- End to end through `cli.main`: stdout, stderr and the exit code for a task
  with open questions and for a failure.
- The contract test: foundry's `LOG.md` spelling equals `git_hooks.LOG_FILE`.

## Terms and decisions
- GLOSSARY.md, "Log": add what makes a question open: an `Asks <id>` line with
  no `Answers <id>:` line after it.

## Open questions
- None.
