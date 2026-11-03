# Task wcf-0027: Close and reopen tasks

## Goal
Add `foundry task close` and `foundry task reopen`, so that finished tasks leave the set of live ones.
To make that possible, move each task's notes from `.agent/<id>/` to `.agent/tasks/open/<id>/` or
`.agent/tasks/closed/<id>/` on `agent-notes`.
Listing `.agent/tasks/open/` on `agent-notes` then shows exactly the tasks still in progress.
The notes root stays `.agent/`, so the pre-commit hook keeping notes off task branches covers both
open and closed tasks without changing.

## Acceptance criteria
- [ ] `foundry task create PROJECT TASK` writes the task template to `.agent/tasks/open/<id>/` on `agent-notes`.
- [ ] `foundry task create` refuses, pushing nothing, when `.agent/tasks/open/<id>/` or `.agent/tasks/closed/<id>/` exists. The message names the existing dir.
- [ ] A new sandbox's `AGENT_TASK_NOTES_DIR` is `.agent/tasks/open/<id>` and its `AGENT_TASK_FILE` is `.agent/tasks/open/<id>/TASK.md`. `AGENT_NOTES_ROOT` stays `.agent`.
- [ ] `foundry task close PROJECT TASK` moves `.agent/tasks/open/<id>/` to `.agent/tasks/closed/<id>/` with every file unchanged, in one commit titled `Close task <id>`, signed with your key and pushed to `agent-notes`. No other path on `agent-notes` changes.
- [ ] `foundry task reopen PROJECT TASK` makes the reverse move, unchanged, in one signed commit titled `Reopen task <id>`, pushed to `agent-notes`.
- [ ] `close` refuses, pushing nothing, with a message saying the task is already closed when it is under `closed/`, and a different message saying it doesn't exist when it is under neither.
- [ ] `reopen` refuses, pushing nothing, with a message saying the task is already open when it is under `open/`, and a different message saying it doesn't exist when it is under neither.
- [ ] Neither `close` nor `reopen` asks for confirmation, reads `TURN`, checks the pull request, or touches `task/<id>`, sandboxes or `sessions/`.
- [ ] Without a signing key, `close` and `reopen` push nothing and give the same signing message `create` gives.
- [ ] `foundry run PROJECT [ROLE] TASK` refuses a closed task, with or without ROLE, before creating or attaching any sandbox. The message says the task is closed and gives the `foundry task reopen` command.
- [ ] `foundry run` without ROLE reads `TURN` from `.agent/tasks/open/<id>/TURN`.
- [ ] The README's command table lists `foundry task close` and `foundry task reopen`, and its `agent-notes` row shows the new layout. `tests/test_docs.py` passes.
- [ ] `GLOSSARY.md` and ADR 0012 are updated as "Terms and decisions" says.
- [ ] The PR description contains the one-off bash snippet that moves the existing `.agent/<id>/` dirs on `agent-notes` to `.agent/tasks/closed/<id>/`.
- [ ] The host tier, ruff and mypy pass, as `CONTRIBUTING.md` describes.

## Out of scope
- Moving the existing tasks on any project's `agent-notes`. The owner runs the snippet from the PR by hand after merging.
- Detecting or refusing sandboxes created before this change, whose recorded `AGENT_TASK_NOTES_DIR` is still `.agent/<id>`. The owner deletes them locally.
- Deleting or changing `task/<id>`, sandboxes or `sessions/` dirs on close.
- Checking `TURN` or the pull request's state before closing.
- Any change to the git hooks or the Claude hooks in `src/agent_runtime/`.
- A command to list tasks.

## Context
- `src/foundry/task.py`: `NOTES_ROOT`, `Task.task_notes_dir`, `create` and `read_turn`. This is the one place a task's names are spelled (ARCHITECTURE.md design rule 1). The open and closed paths belong here.
- `src/foundry/commands/task.py`: the `create` action and its composition root. `close` and `reopen` follow the same shape.
- `src/foundry/project_clone.py`: `ProjectClone`, the only route to the project's repository from foundry (design rule 3). It has no move operation yet.
- `src/foundry/commands/run.py`: reads the turn through `read_turn`. The closed-task refusal goes here.
- `src/foundry/session.py`: builds the session variables from `Task`. It needs no change beyond what `Task` gives it.
- `tests/test_task.py`: runs `foundry.task` against a real bare repository with a stand-in SSH signer. This is the pattern for the new tests.
- `tests/test_run.py`, `tests/test_session.py`, `tests/test_task_contract.py`, `tests/test_docs.py`: these spell or check the old `.agent/<id>` path or the command table.
- Docs that spell the old path: `README.md` ("Where agent output lives" table), `GLOSSARY.md` ("Task notes dir"), and ADR `docs/adr/0006-a-task-is-two-branches.md`. Accepted ADRs aren't edited (`docs/adr/README.md`).
- The `foundry-agent-branches` ruleset in `config/repo-policy/rulesets.yaml` requires signed commits and forbids force-pushes on `agent-notes`. Commits must be signed, and pushes must not be forced.
- No new dependencies.

## Seams to test
- `foundry.task` functions (create, close, reopen, reading the turn) against a real bare repository, as in `tests/test_task.py`. This catches wrong paths, files changed in a move, unsigned commits, and refusals that still push.
- `Task` properties. These catch the notes dir and task file drifting from the session variables.
- `foundry.commands.run` (`prepare_launch` or `role_for_turn`, as `tests/test_run.py` uses them). This catches a closed task reaching a sandbox.
- `cli` argument parsing for `task close` and `task reopen`. This catches missing or misnamed arguments.
- `tests/test_docs.py`. This catches a README command table that disagrees with the code.

## Terms and decisions
- GLOSSARY.md, "Task notes dir": `.agent/tasks/open/<id>/` for an open task, `.agent/tasks/closed/<id>/` for a closed one.
- GLOSSARY.md, new "Open task" and "Closed task": whether the task's notes dir is under `open/` or `closed/`. `foundry task close` and `reopen` move it between the two.
- ADR `docs/adr/0012-...md`: task notes are split into open and closed under `.agent/tasks/`, superseding the notes layout in ADR 0006. Considered options: a separate `.agent-archive/` root, rejected because hooks would need a second root; a migrate command, rejected because the migration is a one-off. Add it to the "Projects and tasks" row in `docs/adr/README.md`.

## Open questions
