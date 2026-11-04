# Task wcf-0029: Task ids follow one pattern, and are never lowercased

## Goal
Every task id has the form `<prefix>-<number>`, such as `wcf-0042`: lowercase ASCII letters, a
hyphen, then four or more digits. Today foundry lowercases every id it is given, in every command
and wherever a `Task` is built, which hides typos and leaves two spellings for one task. After this
task, a `Task` can only hold an id that matches the pattern, foundry never changes the case of an
id, and an id that doesn't match is refused with a message that says what a valid id looks like.

## Acceptance criteria
- [ ] `Task(id, status)`, `Task.as_open(id)` and `Task.as_closed(id)` accept exactly the ids that
      fully match `[a-z]+-[0-9]{4,}`: e.g. `wcf-0042`, `a-0000`, `wcf-10000`.
- [ ] They raise `FoundryError` for every other id, including `WCF-0042`, `Wcf-0042`, `wcf-042`,
      `wcf0042`, `wcf-`, `-0042`, `w2-0042`, `wcf_0042`, `wcf-0042.lock`, `fix-login.2`, `t1`, `7`,
      `Kcf-0042` (Kelvin sign), and the empty string.
- [ ] That error message is exactly `task id '<id as given>' is not valid: use lowercase letters,
      '-', then four or more digits (e.g. wcf-0042)`, with the id `repr`-quoted as now.
- [ ] No code under `src/foundry/` changes the case of a task id: `foundry task create`, `close`,
      `reopen` and `foundry run` given `WCF-0042` each fail with that message, and write, push or
      launch nothing.
- [ ] `SessionVariables.from_env` given `AGENT_TASK=WCF-0042` raises that `FoundryError`.
- [ ] `Task.from_id_and_status` no longer exists.
- [ ] `README.md` no longer says task ids are lowercased; it states the pattern, with an example,
      and that an id not matching it is refused.
- [ ] `GLOSSARY.md`'s "Task id" entry states the pattern.
- [ ] The host tier, ruff and mypy pass, as `CONTRIBUTING.md` describes.

## Out of scope
- A per-project prefix (e.g. tying `wcf` to the project in `config/foundry.yaml`): any prefix is
  accepted. A possible follow-up.
- Renaming or migrating existing tasks: all of them (`wcf-0025` to `wcf-0029` on `agent-notes`)
  already match.
- The lowercasing in `src/foundry/session.py` (`_slug`, line 162): it makes sandbox names, not
  task ids.
- Changing the repo policy rulesets: they match `task/*`, which still holds.

## Context
- `src/foundry/task.py`: `_TASK_ID` (line 34) and its comment, `Task.__post_init__`,
  `Task.from_id_and_status` (line 67), `as_open`, `as_closed`, and the class docstring that gives
  `"WCF-0042"` as an example. Today `__post_init__` also checks `..` and `.lock`; the pattern
  makes those checks redundant.
- `src/foundry/project_tasks.py`: every operation builds `Task`s through `as_open`/`as_closed`,
  so the refusal reaches all of them through `Task`.
- `src/foundry/session.py:86`: `SessionVariables.from_env` builds the task with `Task.as_open`.
- `src/foundry/commands/task.py` and `src/foundry/commands/run.py`: the CLI; their `TASK` help
  says "task id, e.g. wcf-0042", which still holds.
- `README.md:33` ("Task ids are lowercased…") and `GLOSSARY.md:35` ("Task id").
- Many tests use ids that will be refused and must move to valid ones (e.g. `t1` → `tst-0001`,
  `WCF-0042` → `wcf-0042`): `tests/test_task.py` (including `test_valid_task_ids`, the refused-ids
  test, and the uppercase `create`/`close`/`reopen` cases at lines 205, 343, 419 and 434),
  `tests/test_run.py`, `tests/test_session.py`, `tests/test_task_contract.py`,
  `tests/support/__init__.py`, `tests/agent_runtime/test_contract.py`,
  `tests/agent_runtime/test_git_hooks.py`, `tests/sandbox_image/test_git_hooks.py` (docker tier)
  and `tests/sbx/test_smoke.py` (`sbx-smoke`, sbx tier). A test that asserted lowercasing now
  asserts refusal instead.
- Follow `AGENTS.md`'s "Writing" rules for the message and docs.

## Seams to test
- `Task` construction (`Task`, `as_open`, `as_closed`): catches ids accepted or refused against
  the pattern, and the message wording.
- `ProjectTasks.create_task` / `close_task` / `reopen_task` / `get_task_by_id`, through the
  existing origin-repo fixtures in `tests/test_task.py`: catches an uppercase id being lowercased
  or found, and anything being pushed for a refused id.
- `SessionVariables.from_env`: catches an id from a sandbox's environment slipping past the pattern.
- `tests/test_docs.py`: catches broken links or paths in the changed README and glossary.

## Terms and decisions
- GLOSSARY.md, "Task id": "A task's name: lowercase ASCII letters, `-`, then four or more digits,
  such as `wcf-0042`. foundry never changes its case." No ADR.

## Open questions
