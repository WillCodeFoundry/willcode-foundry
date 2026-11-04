# Task wcf-0031: Hand a task's turn on with a command, logged

## Goal
Today, to hand a task to another role you check out `agent-notes`, edit the
task's `TURN` by hand, then commit and push. Nothing checks what you write, so a
typo shows up only at the next `foundry run`. Naming the role to `foundry run`
instead starts it once but leaves `TURN`, and so `task list`, saying the old
turn. Nothing in the task's `LOG.md` says the human moved the turn, so the next
role can't see why it is its turn. Add `foundry task turn PROJECT TASK ROLE`.
It checks ROLE, writes it to `TURN`, appends an entry to `LOG.md` saying who
had the turn and who has it now, with an optional note, and pushes both in one
commit.

## Acceptance criteria
- [ ] `foundry task turn PROJECT TASK ROLE [--note TEXT]` on an open task
      writes `ROLE` followed by a newline to the task's `TURN`, appends one
      entry to its `LOG.md`, and pushes both to `agent-notes` in one commit
      signed with your key, as `close` does. The commit message is
      `Turn of task <id>: <old> → <new>`.
- [ ] ROLE must be a role in `config/foundry.yaml` or `human`. Anything else
      is refused with exit 1, before the repository is read, with a message
      that names ROLE and lists the known roles and `human`.
- [ ] An unknown project is refused as `foundry task create` refuses it, and a
      task id that isn't valid as `create` refuses it, before the repository is
      read.
- [ ] `--note` text that is empty, only blanks, or holds a line break is
      refused with exit 1, before the repository is read.
- [ ] Each of these is refused with exit 1, an `error: <message>` line on
      stderr, nothing on stdout, and no commit or push: the task doesn't exist,
      or is both open and closed (the messages `get_task_by_id` gives); the
      task is closed, with a message saying to reopen it first; `TURN` already
      says ROLE, with a message saying so; the task has no `LOG.md`, or it
      isn't a file, with a message naming the task and the file; no signing
      key (as `close` without one).
- [ ] `<old>` is the stripped text of `TURN`, or `none` when `TURN` is
      missing, empty or only blanks. Such a task is not refused: the command
      writes its `TURN`.
- [ ] The entry appended to `LOG.md` is, after the existing text unchanged
      byte for byte (a newline added first if the file didn't end with one),
      a blank line, then:
      ```
      ## <n> · human · turn
      Turn: <old> → <new>.
      Note: <text>
      ```
      The `Note:` line is there only when `--note` was given, with its text
      stripped. The file ends with a newline.
- [ ] `<n>` is one more than the number in the last line of `LOG.md` that
      starts `## <digits> · `, or `1` when no line does.
- [ ] On success it prints on stdout `task <id> in <PROJECT>: turn <old> →
      <new>`, then `run it with: foundry run <PROJECT> <id>`. The second line
      is left out when the new turn is `human`. It exits 0.
- [ ] `LOG.md` is spelled once on foundry's side, as `LOG_FILE` in
      `src/foundry/task.py`, and a test in `tests/test_task_contract.py` holds
      it equal to `LOG_FILE` in `src/agent_runtime/git_hooks.py`.
- [ ] The README's command table lists `foundry task turn PROJECT TASK ROLE`,
      so `tests/test_docs.py` passes. The README paragraph on `TURN` names the
      command where it now says to edit `TURN`. `ARCHITECTURE.md`'s codemap
      row for `project_tasks.py` mentions handing on the turn.
- [ ] `agent-kit/AGENTS.md`'s "`LOG.md`" section has one sentence saying an
      entry headed `human · turn` is the human handing the turn on.
- [ ] The host tier, ruff and mypy pass.

## Out of scope
- Waiting for, or reusing, wcf-0030's log reading. wcf-0030 also plans
  `LOG_FILE` in `src/foundry/task.py`: whichever merges second reuses the
  other's. Replacing this task's entry-number helper with wcf-0030's log module
  is a follow-up.
- Checking that a hand-off is allowed by the outcome table in
  `agent-kit/AGENTS.md`: any role or `human` may follow any other (ADR 0011).
- Handing on a closed task, or several tasks at once.
- Creating a `LOG.md` for a task that has none (tasks begun with
  `PROGRESS.md`).
- Retrying when the push is refused because someone pushed first: the error
  says so, and you run the command again.
- Starting the role, or answering questions in the log.
- Changing `get_task_by_id`, `read_task_turn`, `list_open_task_summaries`,
  `close_task` or `reopen_task`'s behaviour.
- A new ADR.

## Context
- `src/foundry/commands/task.py`: add `turn` beside `create`, `close`,
  `reopen` and `list`, taking the shared `task_arguments` plus `ROLE` and
  `--note`. Update the `task` help text and the module docstring. Its `main`
  is a composition root that only builds and passes (design rule 7 in
  `ARCHITECTURE.md`). Print through `report`/`Outcome`, or a sibling of them,
  as `close_main` does.
- Errors: raise `FoundryError` and let `cli.main` print it as
  `error: <message>` and exit 1 (design rule 6).
- `src/foundry/project_tasks.py`: add the method beside `close_task`.
  `get_task_by_id` checks out `agent-notes`, so the change is made on the
  commit the task was found on. `_move` shows the write, `commit` and
  `push_atomic(from_remote={}, from_local=[NOTES_BRANCH])` steps.
  `_read_fetched_turn` and `NotOnBranchError` show reading `TURN`.
- `src/foundry/project_clone.py`: `write`, `exists`, `commit`, `push_atomic`,
  `fetched_read`.
- `src/foundry/commands/run.py`: `role_for_turn` refuses a turn that isn't a
  role, listing the known roles; follow its wording. `config.Config.roles`
  holds the roles; `config.Config.project` raises the unknown-project error.
- `src/foundry/task.py`: the one place a task's names are spelled (design rule
  1): `NOTES_BRANCH`, `TURN_FILE`, `HUMAN`, `Task.turn_file`. Add `LOG_FILE`
  here; `src/agent_runtime/git_hooks.py` may not be imported by foundry
  (design rule 2, `tests/test_runtime_boundary.py`).
  `test_agents_md_spells_the_turn_file_and_the_human_s_turn_as_task_py_does`
  in `tests/test_task_contract.py` shows the contract-test pattern.
- The `LOG.md` format: `agent-kit/AGENTS.md` ("`LOG.md`"), GLOSSARY.md
  ("Log") and `docs/adr/0013-roles-talk-through-a-log.md`. `pre-commit` keeps
  it append-only in sandboxes; foundry's scratch clone has no hooks, so the
  append-only rule is this task's to keep.
- `docs/adr/0011-turn-is-one-line.md`: `TURN` is one line, and nothing checks
  a hand-off. This command checks only that ROLE is a role or `human`.
- `tests/test_task.py`: real repositories in temporary folders (`origin_dir`,
  `git_env`, `project_tasks_of`), signed-commit and push-nothing tests for
  `close` (`test_close_moves_the_task_notes_dir_unchanged_in_one_signed_commit`,
  `test_close_and_reopen_refuse_and_push_nothing`,
  `test_without_a_signing_key_close_and_reopen_push_nothing`), parser tests
  (`test_close_and_reopen_take_a_project_and_a_task`). Tests never patch
  (design rule 3).
- No new dependencies.

## Seams to test
- The function that builds the new `LOG.md` text from the old text, the old
  and new turns and the note, called with plain strings: an empty log, a log
  with entries, a last heading that isn't the highest number, a file without
  a final newline, with and without a note. Catches numbering, spacing and any
  change to the existing text.
- The `ProjectTasks` method, against a real repository in a temporary folder:
  `TURN` and `LOG.md` after the push, one signed commit and its message; a
  missing or empty `TURN`; each refusal (not found, closed, same turn, no
  `LOG.md`, no signing key) pushing nothing. Catches writing the wrong dir,
  a second commit, and pushing after a refusal.
- The checks made before the repository is read (ROLE, note, project, task
  id), called with plain values and the config. Catches an unchecked value
  reaching git.
- The function that turns the result into stdout lines: with and without the
  `run it with` line. Catches formatting bugs.
- The parser: `task turn` takes a project, a task, a role and an optional
  `--note`, as `test_close_and_reopen_take_a_project_and_a_task` checks.
- End to end through `cli.main`: stdout, stderr and the exit code for a
  hand-off and for a refusal.
- The contract test: `task.LOG_FILE` equals `git_hooks.LOG_FILE`.

## Terms and decisions
- GLOSSARY.md, "Log": add that the human can hand the turn on with
  `foundry task turn`, which appends an entry headed `human · turn`.

## Open questions
- None.
