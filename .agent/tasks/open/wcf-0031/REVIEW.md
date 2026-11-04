# Review

## Round 1 (reviewing 7b35b61)

Reviewed `git diff 994be5e...7b35b61` (commits 48ffcc6, 889c2a6, 6e5dc3c, 0fdb66d, f644589 and 7b35b61). It was checked against `TASK.md` as of f2a97c5, which is signed by the planner's identity. The planner shares that identity with the architect, so the two can't be told apart. `TASK.md`'s only other commit is cabaf3b, the human's `Add task wcf-0031`. No other role changed it. The task has no `DESIGN.md`.

Checks run at 7b35b61 in a throwaway clone: the host tier (747 passed), ruff check, ruff format --check and mypy all pass.

### Standards

What holds up: design rules 1, 2, 3, 6 and 7, and ADRs 0011 and 0013. `LOG_FILE` is spelled once and held equal to the hooks' copy by a contract test. `turn_main` only builds and passes. Nothing is patched. The log stays append-only.

- **R1 (Follow-up).** `src/foundry/project_tasks.py:143-144`, the `hand_on_turn` docstring. "Relies on get_task_by_id having just found ``task`` open: it checked out NOTES_BRANCH, so the change is made on the commit the task was found on." The sentence runs past 25 words and chains its reasons behind a colon and "so". That breaks the "Writing" rules in `AGENTS.md`. Whoever calls `hand_on_turn` meets it, and the precondition that matters gets buried. Direction: one sentence for the precondition, one for the reason.
- **R2 (Follow-up).** `README.md:35`, the `TURN` paragraph. It was already about nine sentences long, against the three-sentence rule in "Writing". The diff adds a sentence that chains reasons behind a colon: "run `foundry task turn`: it writes `TURN` … so the next role sees why". Direction: move the "hand it on yourself" sentences into their own short paragraph. Accepting it as is is also fine, since the length was there before this change.

### Spec

No findings. Every acceptance criterion is met by code and a test, or by a check that was run:

- `hand_on_turn`: `test_hand_on_turn_writes_turn_and_appends_to_the_log_in_one_signed_commit`.
- The checks before git: `test_turn_arguments_are_refused_before_any_git` (project, task id, ROLE, and a note that is empty, blank, `\n`, `\r` or U+2028).
- The refusals that push nothing: `test_hand_on_turn_refuses_and_pushes_nothing` and `test_without_a_signing_key_hand_on_turn_pushes_nothing`.
- `none` for a missing or blank `TURN`.
- The entry format and its numbering: `test_the_turn_entry_follows_the_log_unchanged_…`.
- `turn_report`, and the run end to end through `cli.main`.
- The `LOG_FILE` contract test.
- The docs, with `tests/test_docs.py` passing.
- `agent-kit/AGENTS.md` and GLOSSARY "Log".

The CRLF and non-UTF-8 departures from "byte for byte" are the human's call (LEARNINGS.md, entry 4). So is `ProjectClone.write` refusing a link. Both are accepted as is.

### Behaviour

Tried and found sound:
- a missing, blank or padded `TURN`;
- a `LOG.md` that is a folder or a link, and a `TURN` that is a link (each refused, with nothing pushed);
- no signing key (fails at commit, before the push);
- a note holding `\r` or NEL;
- a log with no final newline, and the template's `# Log\n`.

- **R3 (Design question).** `src/foundry/project_tasks.py:159-166` appends to the task's `LOG.md` on `agent-notes`. `agent-kit/AGENTS.md:258` tells every role that `pull --rebase` on the notes branch "never conflicts", because each agent touches only its own task's dir.
  - That no longer holds. Suppose a role's session for the task has committed a `LOG.md` entry but not yet pushed it, and the human runs `foundry task turn` meanwhile. The agent's next `git pull --rebase` then stops with `CONFLICT (content): Merge conflict in …/LOG.md`, and both entries have the same number.
  - Who hits it: the human, in the case `TASK.md` gives as the command's reason. They start a role with `foundry run P T <role>`, then run `foundry task turn` while that session is still going, to correct `task list`. Sessions last long, so the two needn't happen within seconds of each other. Reproduced with the `origin_dir`, `edit_notes` and `hand_on` helpers.
  - Nothing is lost, but the agent has been told this cannot happen. It has no instruction for resolving the conflict, and it can't end its session with the rebase unfinished.
  - Why it isn't the dev's alone to fix: every fix either changes the documented rule in `agent-kit/AGENTS.md` or scripts a recovery. Telling the human not to hand on a task while its role is running would also be a new rule. Which one to choose is for the architect and the human.
- **R4 (Follow-up).** `src/foundry/project_tasks.py:149` only strips `TURN`, so a `TURN` that holds more than one line goes whole into the `Turn:` line and the commit message (`:165`).
  - With `TURN` = `reviewer\n## 7 · x\n`, the log gets a line `## 7 · x → dev.`. That line reads as a heading, so later entries are numbered from it.
  - Who hits it: the human, about once, when using `turn` to repair a hand-edited `TURN` that `foundry run` refused. The command does still repair `TURN`. Reproduced.
  - Direction: treat a `TURN` of more than one line like a blank one, or refuse it with a message.

### Smells

Functions:

| Function | Status |
|---|---|
| `task.py:Task.log_file` | new, clean |
| `project_clone.py:ProjectClone.write` | clean |
| `project_tasks.py:ProjectTasks.hand_on_turn` | new, R5, R6 |
| `project_tasks.py:ProjectTasks._read_fetched_turn` | clean, simpler than before |
| `project_tasks.py:ProjectTasks._read_fetched_turn_text` | new, clean |
| `project_tasks.py:log_with_turn_entry` | new, clean |
| `commands/task.py:add_parser` | clean |
| `commands/task.py:turn_main` | new, R9 |
| `commands/task.py:require_turn_arguments` | new, R8 |
| `commands/task.py:hand_on_open_task_turn` | new, R7 |
| `commands/task.py:turn_report` | new, clean |
| the tests in `tests/test_task.py` and `tests/test_task_contract.py` | clean |

- **R5 (Follow-up), possible Duplicated Code.** `src/foundry/project_tasks.py:165-166` repeats `_move`'s `commit` and then `push_atomic(from_remote={}, from_local=[NOTES_BRANCH])` (`:213-214`). Whoever adds the out-of-scope push retry would have to edit both places. Direction: one private "commit and push NOTES_BRANCH" step.
- **R6 (Follow-up), possible Long Function.** In `src/foundry/project_tasks.py:139-167`, the turn is read through a helper, but the log read and its error translation are inline (`:153-158`). That is a lower level of detail than the rest of the method. The wcf-0030 merge will edit here. Direction: extract the log read, as the turn read was extracted.
- **R7 (Follow-up), possible Feature Envy.** At `src/foundry/commands/task.py:183-186`, the lookup and the closed refusal sit in the command, while `close_task` and `reopen_task` keep them in `ProjectTasks`. As a result, `hand_on_turn` repeats the check as an `assert` (`project_tasks.py:148`), and the module docstring has to name an exception. This was a deliberate choice (LOG.md, entry 5), so the message can name the project. Direction: accept as is.
- **R8 (Follow-up), possible Duplicated Code.** `src/foundry/commands/task.py:166-168` copies the shape of `role_for_turn`'s "known: …, or human" listing (`commands/run.py:75-78`). Direction: one helper that formats the known roles, when either listing next changes.
- **R9 (Follow-up), possible Data Clumps.** `src/foundry/commands/task.py:110-120` unpacks `project_name`, `task_id`, `role_name` and `note` from `args` twice. Direction: accept as is.

### Names

At the human's request, this section was checked again against the names renamed in earlier tasks' reviews (wcf-0027 R22–R26, wcf-0028 R11–R15 and their NAMES.md). The human ruled each of those Blocking. That check added R11–R13 and the second point of R10.

Clean: `LOG_FILE`, `Task.log_file`, `TurnChange` and its `task`, `before` and `after`. Also clean: `hand_on_turn`, `_NO_TURN`, `_LOG_HEADING`, `log_with_turn_entry`, `turn_main`, `hand_on_open_task_turn`, `turn_report`, `found`, `known`, the CLI's `foundry task turn`, `ROLE` and `--note`, and the test names and helpers. `ProjectClone.write`'s new refusal is clean too. The added prose (README, GLOSSARY, `agent-kit/AGENTS.md`, ARCHITECTURE, docstrings) breaks no agreed word.

- **R10 (Blocking), an instance named otherwise.** A `TurnChange` is named `change` at `src/foundry/commands/task.py:118` and `:189` (the `turn_report` parameter), and at `tests/test_task.py:699`.
  - The python-naming skill names an instance for its class unless its scope holds two of the type or its role is what the reader needs. Neither applies here.
  - `turn_report(project_name, change: TurnChange)` at `:189` sits beside `report(outcome, project_name, changed: task.Task)` at `:149`. Those are sibling functions in one module, with parameters a letter apart that hold different types. That is the `list_project` and `list_projects` clash wcf-0028 renamed (R13 there).
  - In `commands/`, `change` already holds a `RulesetChange` (`commands/repo.py:60`), so the word names two types in sibling modules.
  - Who hits it: the next reader of `turn_report`, or of a search for `change.` across `commands/`.
  - Direction: name it for its class. The `repo.py` drift is older, so list it as a follow-up and don't rename it here.
- **R11 (Blocking), `role_name` holds a turn, not a role.**
  - In `src/foundry/commands/task.py`, `require_turn_arguments` (`:157`) and `hand_on_open_task_turn` (`:177`) take `role_name`, and the parser's dest is `role_name` (`:60`). The value may be `human`.
  - GLOSSARY.md's "Turn" is "which role works on a task next, or `human`". Its "Role" (planner, dev, qa, reviewer or architect) doesn't include `human`.
  - The code says so itself at `:166-168`: `if role_name != task.HUMAN and …`, then "`{role_name!r}` is not a role".
  - At `:186` the same value becomes `turn`, in `hand_on_turn(found, role_name, …)`, so one value has two names on its way through.
  - Everywhere else in `src/foundry` (`config.py`, `run.py`), `role_name` holds only a role. This use is a homonym, and a synonym for the glossary's word.
  - Who hits it: the next reader of the turn command's checks, every time they read `:157-186`.
  - Direction: name the value for the glossary's word, as `hand_on_turn` does. `ROLE` as the metavar stays, since TASK.md fixes it.
- **R12 (Blocking), `_read_fetched_turn_text` beside `_read_fetched_turn`.**
  - At `src/foundry/project_tasks.py:186` and `:198`, the two names differ only by `_text`, and both return the text of TURN_FILE as a `str`.
  - What differs is the contract. `_read_fetched_turn` refuses a missing or blank TURN_FILE. `_read_fetched_turn_text` returns `""`.
  - wcf-0028 turned down `_read_turn` for the same reason: a near-twin of `read_task_turn` with a different contract.
  - Who hits it: whoever next reads a turn in `ProjectTasks`, choosing between the two.
  - Direction: name it for what sets it apart, the empty result for a missing or blank TURN_FILE.
- **R13 (Blocking), `require_turn_arguments` names its checks but not what it returns.**
  - At `src/foundry/commands/task.py:156`, it returns the `Project`. It is called as `project = require_turn_arguments(...)` (`:110`).
  - wcf-0027 renamed `role_to_launch` (R25 there) so that the name gives both the check and the result: `require_open_task_and_role`, which this function's NAMES.md row cites.
  - The other `require_` names in the code, `_require_fetched` and `_require_on_branch`, return nothing.
  - Who hits it: a reader of `turn_main`, or of the `require_` helpers.
  - Direction: name the result as well as the check, as `require_open_task_and_role` does.

### Design questions

- **R3**, against the documented rule in `agent-kit/AGENTS.md` ("Notes checkout": `pull --rebase` "never conflicts"). Appending to a task's `LOG.md` from outside its session breaks that rule. Should the rule change, should the human be told not to hand on a task while its role is running, or should something else be done? No other finding waits for it.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| Standards | 2 | 0 | R1, the docstring sentence |
| Spec | 0 | 0 | |
| Behaviour | 2 | 0, plus 1 design question open | R3, a `LOG.md` rebase conflict for a running role |
| Smells | 5 | 0 | R5, the duplicated commit-and-push |
| Names | 4 | 4 | R11, `role_name` for a turn that may be `human` |

Verdict: changes needed
