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

## Round 2 (reviewing fc0c99c)

Reviewed the fix diff `git diff 7b35b61...fc0c99c` (21e59a9 to fc0c99c, 19 commits), judging round 1's findings by `LOG.md` entry 10 and the changes in entries 11–22. The spec of record is `TASK.md` as of f2a97c5, signed by the planner's identity, which the architect shares. `DESIGN.md` is as of 9b086e2, signed by the architect's identity, and no other role changed it.

Checks run at fc0c99c in a throwaway clone: the host tier, `ruff check`, `ruff format --check` and mypy all pass.

### TASK.md changed by another role

Three commits signed by the dev changed `TASK.md`. The dev is not an allowed signer for it:

| Commit | Signer | Message |
|---|---|---|
| 9b1e640 | wc-foundry-dev (G) | `wcf-0031: progress` |
| e345039 | wc-foundry-dev (G) | `wcf-0031: progress` |
| 1cfac67 | wc-foundry-dev (G) | `wcf-0031: ready-for-review` |

Together they (`git -C "$AGENT_NOTES_DIR" diff f2a97c5 1cfac67 -- .agent/tasks/open/wcf-0031/TASK.md`):
- rename the command to `foundry task handoff` and the heading to `human · handoff`, and change the title, Goal, out of scope, Context, seams and terms to match;
- drop `<old>`, so the commit is `Handoff of task <id> to <ROLE>`, the entry says `Turn: <ROLE>.` and stdout says `handoff to <ROLE>`;
- replace "unchanged byte for byte" with "kept but for the whitespace at the file's end and its line endings".

`LOG.md` entries 16, 20 and 21 say the human allowed each amendment, this once. Only the dev records that, and no commit by the human or the planner does.

- **R14 (Blocking), the code meets a `TASK.md` that no allowed commit wrote.** Against f2a97c5, the code departs from these criteria and out-of-scope lines. The `LOG.md` entry after each attributes it to the human:
  - "`foundry task turn PROJECT TASK ROLE`", "`## <n> · human · turn`", and the README, ARCHITECTURE and `agent-kit/AGENTS.md` wording (entry 16).
  - "`Turn of task <id>: <old> → <new>`", "`Turn: <old> → <new>.`", stdout "`turn <old> → <new>`", and "`<old>` is the stripped text of `TURN`, or `none`" (entry 20).
  - "after the existing text unchanged byte for byte" (entries 13 and 21).
  - Out of scope: "Changing `get_task_by_id`, `read_task_turn`, `list_open_task_summaries` … behaviour". `read_task_turn` and the listing now raise `MissingTurnError`, with one message that says to use `foundry task handoff` (entries 11, 17 and 18). This one isn't in the amended `TASK.md` either: its out-of-scope line is unchanged.
  - `DESIGN.md` still says `foundry task turn`, `human · turn` and "hand on", which the new GLOSSARY "Handoff" lists under _Avoid_.

  Against the dev's amended `TASK.md`, every criterion is met (see Spec).
  - Who hits it: every later reviewer, and anyone checking what the human approved, since the record of the decision is the dev's own say-so.
  - Direction: no code change. The dev asks the planner (`task-question`) to record the amended `TASK.md` with the human, including the out-of-scope line on `read_task_turn` and the listing. It also asks the architect to bring `DESIGN.md`'s names in line, or the human signs both. Round 3 then reviews against that version.

### Round 1's findings

| Finding | Verdict | Why |
|---|---|---|
| R1 | closed | `hand_on_turn`'s docstring is gone. `handoff`'s is new surface (R15). |
| R2 | closed | `README.md:37-41` is three short paragraphs, each reason in its own sentence. |
| R3 | closed | Settled by `DESIGN.md` (9b086e2). Its README sentence is at `README.md:39`. |
| R4 | closed | It no longer applies: `handoff` no longer writes the old turn anywhere. With `TURN` = `reviewer\n## 7 · x\n`, it writes `dev\n`, the entry `Turn: dev.`, and no stray heading (reproduced). |
| R5 | closed | `_commit_and_push` is shared by `handoff` and `_move` (`project_tasks.py:157`, `:208`). |
| R6 | closed | `_read_fetched_log` sits beside `_read_fetched_turn`. |
| R7 | closed | The lookup and the closed refusal are in `ProjectTasks.handoff`, as in `close_task`. The `assert` is gone. |
| R8 | deferred | `commands/task.py:157-159` still copies `role_for_turn`'s listing. The dev defers it to the next change of either. |
| R9 | accepted as is | `handoff_main` passes `task_id`, `turn` and `note` on. That follows from dropping `TurnChange`, and it is no worse than before. |
| R10 | closed | `TurnChange` and `change` are gone. |
| R11 | closed | The value is `turn` from the parser's dest to `handoff`. The metavar stays `ROLE`. |
| R12 | closed | There is one reader now, `_read_fetched_turn`, raising `MissingTurnError`. |
| R13 | closed | `require_valid_handoff_args` returns nothing, and is named for what it requires. |

### Standards

Design rules 1, 2, 3, 6 and 7 hold. So do `CONTRIBUTING.md`'s test layout (helpers in `tests/support/`, fixtures only in the conftests, no patching) and `DESIGN.md`'s "leave alone" list. The docs match the code: the README command table and signing sentence, GLOSSARY "Handoff" and "Log", the ARCHITECTURE codemap, `--help`, and the "has no turn" message.

- **R15 (Blocking, at the human's call).** `src/foundry/project_tasks.py:137-140`, the `handoff` docstring. Its second paragraph has six sentences, against "paragraphs to three sentences" in `AGENTS.md` "Writing". It also lists five refusals in running prose, against "Use a table or a list for anything shaped like one". Whoever needs to know what `handoff` refuses meets it on every read. Direction: put the refusals in a short list, apart from what it writes.
- **R16 (Blocking, at the human's call).** `src/foundry/project_tasks.py:5`, the module docstring, still says "Callers pass task ids, and get Tasks back", but `handoff` returns `None`. Direction: say that `handoff` takes a task id and returns nothing.

### Spec

Against f2a97c5: see R14. Against the dev's amended `TASK.md`, every criterion is met by code and a test or a check that was run:

| Criterion | Shown by |
|---|---|
| TURN, LOG and one signed commit with its message | `test_handoff_writes_turn_and_appends_to_the_log_in_one_signed_commit` |
| ROLE, note and task id refused | `test_bad_handoff_args_are_refused…` |
| Unknown project | the end-to-end test |
| Refusals that push nothing | `test_handoff_refuses_and_pushes_nothing`, `test_without_a_signing_key_handoff_pushes_nothing` |
| A missing or blank `TURN` is written | the `no-turn` and `blank-turn` cases |
| Entry format and `<n>` | `log_with_handoff_entry`'s seven cases |
| stdout | `handoff_lines`, and end to end |
| `LOG_FILE` contract | `test_foundry_spells_the_log_file_as_the_git_hooks_do` |
| Docs | `test_docs` passes, and they were read |
| Host tier, ruff, mypy | the checks run |

`DESIGN.md`'s README sentence is present. Beyond R14, no scope creep was found that the log doesn't attribute to the human.

- **R17 (Blocking, at the human's call).** "refused … before the repository is read" (ROLE, note, task id) holds only by the order of lines in `handoff_main` (`src/foundry/commands/task.py:112-115`). The end-to-end test checks only that nothing was pushed, so moving `require_valid_handoff_args` inside the `with` would still pass. Direction: an end-to-end case that shows a bad ROLE, note or task id is refused before any git runs, for example against a project whose repository doesn't exist.
- **R18 (Blocking, at the human's call).** "the task … is both open and closed (the messages `get_task_by_id` gives)" has no `handoff` case. Only `get_task_by_id`'s own test covers it. `handoff` calls `get_task_by_id` first, so this is shown by reading the code. Direction: add the case to `test_handoff_refuses_and_pushes_nothing`.

### Behaviour

Tried and found sound (reproduced):
- a multi-line, blank, linked or missing `TURN`;
- a log that is empty, holds only blanks, ends in many blank lines, has its highest heading before its last, has an indented `## 5`, or has CRLF in the middle (kept, as the amended criterion allows);
- `foundry run` and `task list` with a blank `TURN`, now refused through `MissingTurnError` with the handoff hint;
- the same-turn refusal raised from inside `suppress(MissingTurnError)`, which still gets through;
- every refusal leaving the origin unchanged.

One bad `TURN` still fails a project's whole `task list`, as at 994be5e. A `TURN` that is a directory makes `handoff` die with an `IsADirectoryError` traceback, and nothing is pushed. That was dropped as a finding, since only a deliberate `mkdir TURN` makes it.

No new findings.

### Smells

| Function | Status |
|---|---|
| `project_tasks.py`: `ProjectTasks.__init__`, `in_scratch_clone`, `read_task_turn`, `list_open_task_summaries`, `_move` | clean |
| `project_tasks.py:_read_fetched_turn` | clean, simpler than before |
| `project_tasks.py:ProjectTasks.handoff` | clean (R5, R6 and R7 closed) |
| `project_tasks.py`: `_read_fetched_log`, `_commit_and_push` | new, clean |
| `project_tasks.py:log_with_handoff_entry` | clean, simpler than before |
| `commands/task.py`: `add_parser`, `create_main`, `close_main`, `reopen_main`, `read_project_listing`, `handoff_lines` | clean |
| `commands/task.py:handoff_main` | R9 |
| `commands/task.py:require_valid_handoff_args` | R8 |
| `commands/run.py`: `main`, `role_for_turn` | clean |
| `tests/support/project_repository.py`: `write_gitconfig`, `make_git_env`, `git_output`, `clone_in` | clean (moved) |
| `tests/support/project_repository.py`: `project_tasks_of`, `ProjectRepository.project_tasks` | R19 |
| `tests/support/project_repository.py`: the other `ProjectRepository` methods | new, clean |
| `tests/conftest.py`: `git_env`, `project_repository` | clean |
| the tests in `test_project_tasks.py`, `test_task_command.py`, `test_project_clone.py`, `test_task.py`, `test_run.py` | clean |

- **R19 (Blocking, at the human's call), possible Duplicated Code.** `tests/support/project_repository.py:53` (`project_tasks_of`) and `:86` (`ProjectRepository.project_tasks`) each build `ProjectTasks(<clone>, "store")`, with the project name spelled twice. mypy flags both sites when the constructor changes, as a49fc8c did, so only the literal can drift. Direction: have one build through the other, or name the project once.

### Names

R10–R13 are closed (see the table above).

Clean:
- `MissingTurnError`, which sits beside `TaskNotFoundError` and `NotOnBranchError`;
- `ProjectTasks.handoff` and `_project_name`, `in_scratch_clone(project, …)`, `_read_fetched_log` and `_commit_and_push`;
- `log_with_handoff_entry` and its `kept`, `handoff_lines`, `require_valid_handoff_args`, `handoff_main` and `HANDOFF_CONFIG`;
- the interface names `foundry task handoff`, `human · handoff` and `Handoff of task <id> to <ROLE>`. None existed on main, so no existing interface was renamed; their mismatch with the `TASK.md` of record is R14;
- the GLOSSARY "Handoff" term, which agrees with ADR 0011 and records the runtime's "handoff to root" under Ambiguities, and the "Log" edit;
- the test helpers `project_repository`/`ProjectRepository`, `seed`, `git_output`, `make_git_env`, `no_signing_key`, `notes_files`, `notes_tree`, `notes_commits` and `notes_signed_with_your_key`, and the renamed test names.

The added prose uses no word the glossary lists under _Avoid_.

- **R20 (Blocking), `ProjectRepository.head()` reads as main's tip but returns agent-notes'.**
  - At `tests/support/project_repository.py:122`, its branch defaults to `NOTES_BRANCH`. The repository is seeded with `--initial-branch=main` (`:134`), so its HEAD is main. Before this round, `head(origin_dir, git_env, branch)` required the branch.
  - Its siblings all name the branch they read: `notes_files`, `notes_tree`, `notes_commits` and `notes_signed_with_your_key`.
  - A call such as `notes_before = project_repository.head()` (`tests/test_project_tasks.py:407`) reads as main's tip. About 17 calls give no branch, so the pattern gets copied.
  - Who hits it: the next author of a `ProjectRepository` test who wants main's tip. An assertion meant for main would quietly check agent-notes.
  - Direction: name it for agent-notes, as its siblings are, or require the branch again.

### Design questions

None open.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| TASK.md changed | 1 | 1 | R14, the code meets a `TASK.md` only the dev wrote |
| Standards | 2 | 2 | R15, `handoff`'s docstring |
| Spec | 2 | 2 | R17, the order of checks is shown only by reading |
| Behaviour | 0 | 0 | |
| Smells | 1 | 1 | R19, the duplicated `"store"` build |
| Names | 1 | 1 | R20, `head()` for agent-notes |

No design questions are open.

At the human's request, after the round was pushed, R15–R19 were relabelled from Follow-up to Blocking and their directions changed from "accept as is" to a fix.

Verdict: changes needed

## Round 3 (reviewing 676d567)

This round reviews the fix diff `git diff fc0c99c...HEAD`, the commits f239d92, 0b4eb6a and 676d567. It judges round 2's findings by `LOG.md` entries 25–29. The spec of record is `TASK.md` as of 8a76f09, signed by the planner's identity, which the architect shares. `DESIGN.md` is as of 4743c4d, signed by the architect's identity. The criteria that 8a76f09 added are checked against the full diff, `994be5e...HEAD`.

Checks run at 676d567 in a throwaway clone: the host tier (746 passed), `ruff check`, `ruff format --check` and mypy all pass.

### TASK.md changed by another role

No new commit. The dev's commits 9b1e640, e345039 and 1cfac67 are still in the file's history, as R14 reported. 8a76f09, signed by the planner's identity (shared with the architect), now records them with the human's approval (`LOG.md` entry 27). That is the version this round reviews against. `DESIGN.md` was changed only by the architect's identity (9b086e2, 4743c4d).

### Earlier findings

| Finding | Verdict | Why |
|---|---|---|
| R8 | deferred | Unchanged; deferred by the dev. |
| R9 | accepted as is | From round 1. |
| R14 | closed | `TASK.md` re-recorded in 8a76f09 and `DESIGN.md` reworded in 4743c4d. The code meets both (see Spec). |
| R15 | closed | `project_tasks.py:136-145`: the first line gives the point, the paragraph has three sentences, and the refusals are a list. |
| R16 | closed | `project_tasks.py:5-6` says `handoff` returns nothing. |
| R17 | closed | `tests/test_task_command.py:291-310`: a stand-in `git` first on `PATH` leaves a mark and fails. A bad ROLE, a blank note, a bad task id and an unknown project each give exactly `("", "error: …\n")` and leave no mark. Behaviour moved `require_valid_handoff_args` inside the `with`, and the test then failed. |
| R18 | closed | The `open-and-closed` case is at `tests/test_project_tasks.py:379-383`. |
| R19 | closed | `ProjectRepository.project_tasks` builds through `project_tasks_of` (`tests/support/project_repository.py:86`). |
| R20 | closed | `head(branch)` requires the branch (`:122`), and `notes_head()` (`:126`) replaces every call that gave none. |

### Standards

Design rule 3 holds. The stand-in `git` goes on `PATH` through `monkeypatch.setenv`, as `CONTRIBUTING.md:42` allows, and no code is patched. The new docstrings keep `AGENTS.md`'s "Writing" rules.

- **R21 (Blocking, at the human's call).** `src/foundry/project_tasks.py:5-6` now names `handoff` as the only exception to "Callers pass task ids, and get Tasks back". But `read_task_turn` (`:127`) returns a `str`, and it did before this task. The fix made an inexact sentence look complete. Who hits it: anyone who reads the module docstring for what its methods return. Direction: make the sentence true of every method, or drop the return-type claim.

### Spec

`TASK.md` at 8a76f09 drops `read_task_turn` and the listing from out of scope, and the human approved the earlier amendments. So the code has no scope creep. `DESIGN.md` at 4743c4d is met: `README.md:39` says to hand a task off only while its role isn't running. Every criterion round 2 tabled is still met. These are the criteria 8a76f09 added:

| Criterion | Shown by |
|---|---|
| `foundry run` refuses a missing, blank or directory `TURN` with the one message | `run.py` → `read_task_turn` → `_read_fetched_turn` (`project_tasks.py:179-194`). `test_a_task_without_a_turn_says_to_hand_it_off` (`tests/test_project_tasks.py:138-152`) covers all three with the full message. |
| `foundry task list` does the same | `project_tasks.py:177`. The test covers only a missing `TURN`, by prefix: R23. |
| handoff refuses a `LOG.md` that is a link | the `log-is-a-link` case, `tests/test_project_tasks.py:401-405` |
| handoff refuses a `TURN` that is a link | `ProjectClone.write`, reached at `project_tasks.py:156-161`. No test covers it: R22. |

- **R22 (Blocking).** The spec says "`TURN` or `LOG.md` is a link, with a message naming it". `test_handoff_refuses_and_pushes_nothing` (`tests/test_project_tasks.py:375-407`) covers only a link `LOG.md`. A probe in a throwaway clone shows the code works: `….agent/tasks/open/tst-0000/TURN is a link: foundry writes only files`, with nothing pushed. But no test in the suite shows it, so a later change to the order of reads and writes could drop it unnoticed. That is the same gap R18 had, which the human made Blocking. Direction: add a `turn-is-a-link` case, with a `LOG.md` present, to that parametrize.
- **R23 (Blocking).** The spec says "`foundry run` and `foundry task list` refuse a task whose `TURN` is missing, not a file, or only blanks, with one message". `test_listing_fails_on_a_task_without_a_turn` (`tests/test_project_tasks.py:468-471`) checks only a missing `TURN`, and only the message's prefix. A probe shows that blank and directory both give the full message. The listing shares its reader with `read_task_turn`, so this is shown only by reading the code, like R18. Who hits it: whoever gives the listing its own reader. Direction: give the listing test the same three cases and the full message.

### Behaviour

No new findings. The stand-in `git` does prove that no git ran:
- `handoff_main` passes the live `os.environ`, and `src/foundry` never resolves git to a fixed path.
- Moving the check inside the `with` made the test fail.
- The PATH change is undone after the test, and the test files pass three runs in a row and in reverse order.

`project_tasks()` through `project_tasks_of` builds the same clone as before.

### Smells

| Function | Status |
|---|---|
| `project_tasks.py`: module docstring, `ProjectTasks.handoff` (docstring only) | clean |
| `tests/support/project_repository.py:ProjectRepository.project_tasks` | clean (R19 closed) |
| `tests/support/project_repository.py:ProjectRepository.head` | clean |
| `tests/support/project_repository.py:ProjectRepository.notes_head` | new, clean |
| `tests/test_project_tasks.py`: the 8 tests moved from `head()` to `notes_head()` | clean |
| `tests/test_project_tasks.py:test_handoff_refuses_and_pushes_nothing` | clean |
| `tests/test_task_command.py:test_handoff_prints_where_the_task_went_or_an_error_and_exits_accordingly` | R24 |

- **R24 (Blocking, at the human's call), possible Duplicated Code.** `tests/test_task_command.py:292-296` builds a stand-in git by hand: a dir, a `#!/bin/sh` script, `chmod`, then the dir first on PATH. The same shape is already in `test_listing_costs_one_fetch_however_many_tasks` (`tests/test_project_tasks.py:503-509`), and in `launch` in `tests/agent_kit/test_session_init.py`. The copies already differ in how they join PATH. The diff adds a copy, and the next dev to add a stand-in on PATH would copy one of the variants. Direction: add a helper in `tests/support/` that writes an executable stand-in and returns its dir for PATH, and use it at both sites in the foundry tests (`tests/test_task_command.py` and `tests/test_project_tasks.py`). Moving `tests/agent_kit/test_session_init.py`'s `sudo` stand-in to the helper is optional.

### Names

R20 is closed (see above). No new findings.

Clean:
- `ProjectRepository.notes_head` and `head(branch)`;
- `project_tasks`, whose body changed but whose result didn't;
- `stand_in_dir` ("stand-in" is the code's word, as in `tests/support/machine.py` and `CONTRIBUTING.md:42`) and `git_ran`;
- the test id `open-and-closed`, and the reworded `handoff` docstring.

The added prose uses no word GLOSSARY lists under _Avoid_. `DESIGN.md` at 4743c4d adds no names and agrees with GLOSSARY "Handoff". "hand on" appears nowhere outside GLOSSARY's own _Avoid_ line.

### Design questions

None open.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| TASK.md changed | 0 new | 0 | R14 closed by 8a76f09 |
| Standards | 1 | 1 | R21, a docstring's return-type claim |
| Spec | 2 | 2 | R22, no test for a link `TURN` |
| Behaviour | 0 | 0 | |
| Smells | 1 | 1 | R24, stand-in setup copied |
| Names | 0 | 0 | |

No design questions are open. R8 is an open Follow-up.

At the human's request, after the round was pushed, R21 and R24 were relabelled from Follow-up to Blocking, and their directions changed to a fix.

Verdict: changes needed

## Round 4 (reviewing c35deda)

This round reviews the fix diff `git diff 676d567...HEAD`, the commits a5f6454, 3364c82, 4d32648, 279a9f3 and c35deda. It judges round 3's findings by `LOG.md` entries 33, 35 and 37. The spec of record is still `TASK.md` as of 8a76f09, signed by the planner's identity, which the architect shares. `DESIGN.md` is as of 4743c4d, signed by the architect's identity.

Checks run at c35deda in a throwaway clone, after `uv sync --group dev`: the host tier, `ruff check`, `ruff format --check` and mypy all pass. `tests/test_project_tasks.py` and `tests/test_task_command.py` pass three runs in a row, swapped, and with the test ids reversed.

### TASK.md changed by another role

No new commit to either file since round 3. The dev's commits 9b1e640, e345039 and 1cfac67 are still in `TASK.md`'s history. 8a76f09 re-recorded them with the human's approval, as round 3 said.

### Earlier findings

| Finding | Verdict | Why |
|---|---|---|
| R8 | deferred | Unchanged; deferred by the dev. |
| R9 | accepted as is | From round 1. |
| R21 | closed | `src/foundry/project_tasks.py:4-6` now says only that "every operation on one task goes through it, and callers pass task ids". That holds for every method that takes a task, and listing is named as the exception. Nothing is left to say what the methods return. |
| R22 | closed | The `turn-is-a-link` case at `tests/test_project_tasks.py:406-414` writes a `LOG.md` and matches the full message, so only `TURN` can be what is refused. Behaviour skipped `ProjectClone.write`'s link check for `TURN` alone, and the case failed. |
| R23 | closed | `tests/test_project_tasks.py:486-500` runs the missing, blank and directory cases, with the full message anchored at both ends. Behaviour removed `.strip()` and the case `blank` failed. It removed the blob-type check and `missing` and `directory` failed. |
| R24 | closed | The hand-built stand-in git is gone from `tests/test_task_command.py`, at the human's call (entry 35). The helper was added in 4d32648 and removed in 279a9f3, so none is left. `test_listing_costs_one_fetch_however_many_tasks` is as on main. No copy of the stand-in shape is left in the task's diff. |

R17's point still holds, shown another way (c35deda). The ROLE, note and task-id refusals now run on project `gone`, whose repository doesn't exist (`tests/test_task_command.py:268-304`). Each must print exactly `error: <message>` and nothing else. A check made after the repository is read would print git's error instead. Behaviour checked this by moving each check after `get_task_by_id` one at a time:
- the whole call;
- the role check alone;
- the note check alone;
- the task-id check (dropped).

All four failed the test. Moving the call inside the `with`, before `handoff`, passes, and that is correct: `ProjectClone.init` only runs `git init` and local config, and doesn't read the repository. `make_git_env` gives git a throwaway `HOME` and `GIT_CONFIG_NOSYSTEM=1`, so nothing in the developer's git config can make `gone` resolve.

### Standards

No new findings. The rewritten module docstring keeps `AGENTS.md`'s "Writing" rules. With the stand-in gone, the test no longer sets `PATH`, so design rule 3 holds trivially.

### Spec

No new findings: nothing missing or partial, and no scope creep. Each criterion that round 3 tabled as partial now has a test: R22 for a link `TURN`, R23 for the listing. The stand-in was dropped at the human's call. Its criterion, "refused … before the repository is read", is shown by the `gone` project, as above. `handoff_main` at `src/foundry/commands/task.py:110-113` makes both checks before `ProjectTasks.in_scratch_clone`.

### Behaviour

No new findings. See R17's point, R22 and R23 above for what each mutation showed.

### Smells

| Function | Status |
|---|---|
| `src/foundry/project_tasks.py`: module docstring | clean (R21 closed) |
| `tests/test_project_tasks.py:test_handoff_refuses_and_pushes_nothing` | clean |
| `tests/test_project_tasks.py:test_listing_fails_on_a_task_without_a_turn` | clean, see below |
| `tests/test_task_command.py:test_handoff_prints_where_the_task_went_or_an_error_and_exits_accordingly` | clean, and shorter (R24 closed) |

The sub-agent raised possible Duplicated Code. `test_listing_fails_on_a_task_without_a_turn` (`:486-500`) has the same three cases and message as `test_a_task_without_a_turn_says_to_hand_it_off` (`:138-152`). I dropped it, because it is exactly what R23's direction asked for. The two tests are of two entry points, and the duplication is what lets either one get its own reader later.

### Names

Clean:
- `turn-is-a-link`, which matches `log-is-a-link`;
- the reflowed ids;
- `files`, which matches `:139`;
- `missing` and `blank`;
- the project name `gone`, which is true of it, with the docstring at `:268` explaining it;
- the prose in `project_tasks.py:4-6` and in the end-to-end docstring.

The added prose uses no word GLOSSARY lists under _Avoid_.

The sub-agent raised the id `directory` (`:489`) as a synonym for "dir" (`log-is-a-dir`, `:422`). I dropped it, for two reasons. It copies the sibling test's ids at `:141`, which came in 0d77ef7 and which round 3 reviewed. And GLOSSARY doesn't list "directory" under _Avoid_. Under python-naming's bar, it could be better but doesn't break an agreed word.

### Design questions

None open.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| TASK.md changed | 0 new | 0 | |
| Standards | 0 | 0 | |
| Spec | 0 | 0 | |
| Behaviour | 0 | 0 | |
| Smells | 0 | 0 | |
| Names | 0 | 0 | |

R21–R24 are closed. No design questions are open. R8 is an open Follow-up, deferred.

Verdict: approved

## Round 5 (reviewing c35deda)

The human asked for this round on 2026-11-06, after round 4 approved c35deda. It reviews no new commits. It adds two findings from a mutation-testing run with mutmut 3.8.1 over `src/`, on the host tier, which the human asked for. The human directs that the dev fix both. The spec of record is unchanged: `TASK.md` at 8a76f09 and `DESIGN.md` at 4743c4d. Neither file has changed since round 4.

### TASK.md changed by another role

No new commit to either file.

### Earlier findings

| Finding | Verdict | Why |
|---|---|---|
| R8 | deferred | Unchanged. |
| R9 | accepted as is | From round 1. |
| R18 | reopened as R26 | The human now asks for the `open-and-closed` case it added to be dropped (see R26). |

R21–R24 stay closed.

### Spec

- **R25 (Blocking, at the human's call).** The spec says the entry carries "`Note: <text>`" when `--note` was given. `handoff_main` passes `note=args.note` (`src/foundry/commands/task.py:114`). No test shows the note getting from the command line into `LOG.md`.
  - `test_handoff_prints_where_the_task_went_or_an_error_and_exits_accordingly` (`tests/test_task_command.py:285-290`) passes `--note go`. It then checks only stdout and the commit message.
  - The `ProjectTasks.handoff` tests call the method with a note directly, so they don't cover the command.
  - I changed line 114 to `note=None` in a throwaway clone, and the whole host tier still passed.
  - Who hits it: anyone who changes `handoff_main` or the `--note` argument, which could silently drop every note.
  - Direction: in the end-to-end test, assert that the task's `LOG.md` after the handoff ends with the note's line.

### Smells

- **R26 (Blocking, at the human's call), redundant test case.** The `open-and-closed` case of `test_handoff_refuses_and_pushes_nothing` (`tests/test_project_tasks.py:379-383`) repeats `test_a_task_in_both_dirs_is_refused_naming_both` (`:195`).
  - `handoff` reaches that refusal only through `get_task_by_id`. The `not-found` case (`:378`) already shows that `handoff` goes through `get_task_by_id`.
  - This reverses R18, which added the case, by the human's choice.
  - Who hits it: the next dev who changes the both-dirs message, who has to edit two tests for one behaviour.
  - Direction: drop the case and its id.

### Standards, Behaviour, Names

Not reviewed again: this round only adds the findings above.

### Design questions

None open.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| Spec | 1 | 1 | R25, the note isn't shown to reach `LOG.md` |
| Smells | 1 | 1 | R26, a test case that repeats another test |
| Others | 0 | 0 | |

R8 is an open Follow-up.

Verdict: changes needed

## Round 6 (reviewing 37ee769)

This round reviews only the fix diff c35deda...37ee769: two test-only commits, f23666d (R25) and 37ee769 (R26). The spec of record is unchanged: `TASK.md` at 8a76f09 and `DESIGN.md` at 4743c4d (both signed by the architect identity the planner shares). Neither file has changed since round 5. The host tier, ruff and mypy pass at 37ee769.

### TASK.md changed by another role

No new commit to either file.

### Earlier findings

| Finding | Verdict | Why |
|---|---|---|
| R25 | closed | `tests/test_task_command.py:291` asserts the task's `LOG.md` ends with `\nNote: go\n` after the `cli.main` handoff. In a throwaway clone, with `handoff_main` passing `note=None`, the test fails. Behaviour also found that it fails if the role is passed as the note, if `Note:` is written before `Turn:`, or if the prefix changes. |
| R26 | closed | 37ee769 drops the `open-and-closed` case and its id together. `test_handoff_refuses_and_pushes_nothing` runs seven cases under seven matching ids, and all pass. The both-dirs message is still tested once, in `test_a_task_in_both_dirs_is_refused_naming_both` (`tests/test_project_tasks.py:195`). |
| R8 | deferred | Unchanged. |
| R9 | accepted as is | From round 1. |

### Standards

No findings. The R25 assertion checks only the end of the file, so it shows that the composition root passes `--note` through (design rule 7). It doesn't repeat the lower tier's format tests, which keeps CONTRIBUTING.md's "each behaviour is tested once" rule. R26's removal keeps to the same rule.

### Spec

No findings. The criterion "the task doesn't exist, or is both open and closed (the messages `get_task_by_id` gives)" still holds. The `not-found` case (`tests/test_project_tasks.py:378`) shows `handoff` refusing through `get_task_by_id`, and `:195` shows `get_task_by_id` giving the both-dirs message. A both-dirs handoff that pushes nothing is now inferred from those two tests rather than tested directly. That falls short of Blocking, and the human chose R26 knowing it.

### Behaviour

No findings. The assertion isn't vacuous and isn't flaky. `notes_files` (`tests/support/project_repository.py:105`) strips the text and then adds a newline, so this assertion can't show the file's final newline. The log-text builder's unit tests cover that.

### Smells

| Function | Mark |
|---|---|
| `tests/test_project_tasks.py:test_handoff_refuses_and_pushes_nothing` | clean |
| `tests/test_task_command.py:test_handoff_prints_where_the_task_went_or_an_error_and_exits_accordingly` | clean |

No findings.

### Names

The diff adds and renames no names. The existing names it touches all stay clean: the two tests above, the remaining parametrize ids and `notes_files`. It adds no prose. No findings.

### Design questions

None open.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| TASK.md changed | 0 new | 0 | |
| Standards | 0 | 0 | |
| Spec | 0 | 0 | |
| Behaviour | 0 | 0 | |
| Smells | 0 | 0 | |
| Names | 0 | 0 | |

R25 and R26 are closed. No design questions are open. R8 is an open Follow-up, deferred.

Verdict: approved

## Round 7 (reviewing 69e1f5f)

This round reviews only the fix diff 37ee769...69e1f5f. The human asked for this change after round 6's approval (LOG entries 45–47). It has two commits:
- d501ddd: `ProjectTasks` raises `ClosedTaskError` and `MissingTurnError` and names no command. `suggesting_fixes` in `commands/task.py` adds the command.
- 69e1f5f: `ProjectTasks.in_scratch_clone` takes a URL again, as on main.

The spec of record hasn't changed: `TASK.md` at 8a76f09 and `DESIGN.md` at 4743c4d, both signed by the architect identity the planner shares. Neither file has changed since round 6. The host tier (752 passed), ruff and mypy pass at 69e1f5f.

### TASK.md changed by another role

No new commit to either file.

### Earlier findings

| Finding | Verdict | Why |
|---|---|---|
| R8 | deferred | Unchanged. `run.py` now imports from `commands/task.py`, so a shared roles listing could use the same import when R8 is taken up. |
| R9 | accepted as is | From round 1. |

R1–R7 and R10–R26 stay closed.

### Standards

No findings.
- `commands/run.py:12` imports `suggesting_fixes` from `commands/task.py`. Design rule 2 limits imports only between foundry, the runtime and `agent_sandbox`, and this import makes no cycle.
- `handoff_main` adding `suggesting_fixes(project.name)` to its `with` (`commands/task.py:114`) still only builds and passes (design rule 7).
- `ClosedTaskError` and `MissingTurnError` are `FoundryError`s (design rule 6). The two errors are raised in three places, and `suggesting_fixes` wraps all three: `handoff_main`, `read_project_listing` and `require_open_task_and_role`.
- Every docstring the diff touches matches the code.

### Spec

No findings. Each message the diff re-routes is still exactly what TASK.md fixes, and a test shows each one:
- **No turn:** `test_a_closed_task_or_one_without_a_turn_is_refused_saying_how_to_fix_it` compares the whole string with `==`. Its wiring is shown by `tests/test_run.py:178` and `tests/test_task_command.py:171`.
- **Closed, through `run`:** `tests/test_run.py:169`.
- **Closed, through `handoff`:** checked end to end through `cli.main`.

The diff leaves `get_task_by_id`, `close_task` and `reopen_task` untouched, as TASK.md's out-of-scope list requires. No scope creep.

### Behaviour

No findings. Reproduced in a throwaway clone:
- No `ClosedTaskError` or `MissingTurnError` reaches the user without its command. `read_task_turn` and `list_open_task_summaries` each have one caller, and it is wrapped. `foundry task list` over several projects goes through the wrapped `read_project_listing`. `run` with an explicit role checks for a closed task inside the wrapped block.
- `suggesting_fixes` is the inner context manager in both combined `with` statements. The error is turned into its message before the scratch clone is removed, and cleanup errors pass through unchanged.
- Both messages are identical, character for character, to 37ee769's.
- The unknown-project refusal still comes before any clone.

### Smells

| Function | Mark |
|---|---|
| `src/foundry/project_tasks.py:ClosedTaskError.__init__` | new; R28 |
| `src/foundry/project_tasks.py:MissingTurnError.__init__` | new; R28 |
| `src/foundry/project_tasks.py:ProjectTasks.__init__` | clean, simpler |
| `src/foundry/project_tasks.py:ProjectTasks.in_scratch_clone` | clean, back to main's shape |
| `src/foundry/project_tasks.py:ProjectTasks.handoff` | clean, simpler |
| `src/foundry/project_tasks.py:ProjectTasks._read_fetched_turn` | clean, simpler |
| `src/foundry/commands/task.py:suggesting_fixes` | new; R27, R28 |
| `src/foundry/commands/task.py:create_main`, `close_main`, `reopen_main`, `handoff_main`, `read_project_listing` | clean |
| `src/foundry/commands/run.py:main` | clean |
| `src/foundry/commands/run.py:require_open_task_and_role` | clean, simpler: its copy of the closed-task message is gone |
| `tests/support/project_repository.py:project_tasks_of` | clean |
| `tests/test_project_tasks.py:test_a_task_without_a_turn_is_refused_naming_its_turn_file`, `test_listing_fails_on_a_task_without_a_turn` | clean |
| `tests/test_project_tasks.py:test_handoff_refuses_and_pushes_nothing` | R29 |
| `tests/test_run.py:project_tasks` (fixture), `test_a_task_without_a_turn_is_refused_saying_how_to_hand_it_off` | clean |
| `tests/test_task_command.py:test_a_closed_task_or_one_without_a_turn_is_refused_saying_how_to_fix_it`, `test_a_listing_refuses_a_task_without_a_turn_saying_how_to_hand_it_off`, `test_handoff_prints_where_the_task_went_or_an_error_and_exits_accordingly` | clean |

- **R27 (Follow-up), possible Divergent Change.**
  - Where: `src/foundry/commands/run.py:12` imports `suggesting_fixes` from `commands/task.py`. No other command module imports a sibling, and ARCHITECTURE.md's codemap gives `commands/` "one module per subcommand", so `commands/task.py` now also changes for `run`'s sake.
  - Who hits it: the next dev who changes `run`'s refusals or splits `commands/task.py`, now and then.
  - Direction: accept as is, or move `suggesting_fixes` into a small shared module in `commands/`.
- **R28 (Follow-up), possible Feature Envy.**
  - Where: `src/foundry/commands/task.py:158` and `:161` join each error's message to its fix. How each joins depends on how the message ends in `src/foundry/project_tasks.py:32` and `:40`: `": "` after `ClosedTaskError`'s, which has no full stop, and `" "` after `MissingTurnError`'s, which ends in one. Rewording either message means editing both files.
  - Who hits it: the next dev who rewords a refusal, rarely.
  - Direction: accept as is, since TASK.md fixes both messages; or add a comment in `suggesting_fixes` naming the dependency.
- **R29 (Follow-up), test logic keyed on one case.**
  - Where: `tests/test_project_tasks.py:428` asserts `isinstance(…, ClosedTaskError) == (task_id == "cls-0000")`, which ties the shared body to one case's task id. A second closed-task case under another id would quietly flip what the assertion checks.
  - Who hits it: the next dev who adds a refusal case, occasionally.
  - Direction: make the expected error type a column of the parametrize table.

### Names

| Name | Mark |
|---|---|
| `ClosedTaskError` | clean: GLOSSARY's "Closed task", beside `TaskNotFoundError` and `MissingTurnError` |
| `suggesting_fixes` | clean: reads well at `with …, suggesting_fixes(project.name):`, with no homonym |
| `url` (parameter of `in_scratch_clone`; local in `run.py:main`) | clean: as on main |
| `in_scratch_clone`, `MissingTurnError`, `ProjectTasks`, `require_open_task_and_role` (behaviour changed) | clean: each name still fits |
| `error` (in `suggesting_fixes`), `turn` (`run.py:66`) | clean |
| `refusal` (test locals) | R30 |
| `test_a_task_without_a_turn_is_refused_naming_its_turn_file`, `test_a_task_without_a_turn_is_refused_saying_how_to_hand_it_off`, `test_a_closed_task_or_one_without_a_turn_is_refused_saying_how_to_fix_it`, `test_a_listing_refuses_a_task_without_a_turn_saying_how_to_hand_it_off` | clean |

- **R30 (Blocking), homonym.**
  - Where: `refusal` names a pytest `ExceptionInfo` around a `FoundryError` at `tests/test_project_tasks.py:426` (used at `:428`) and `tests/test_task_command.py:166` (used at `:168`).
  - The clash: GLOSSARY.md defines **Refusal** as "What a hook or a hardening mode says when it stops something". `tests/agent_runtime/test_git_hooks.py:96` and `:213` use `refusal` that way, for a hook's message string. NAMES.md itself turned "Refusal" down for `suggesting_fixes` for that reason.
  - The agreed word: the tests name other `ExceptionInfo`s `raised`, at `tests/test_project_clone.py:73`, `tests/test_skills.py:206` and `tests/agent_runtime/test_git.py:81`.
  - Who hits it: the next reader of these two tests, who reads `refusal.value` as a hook's message.
  - Direction: name both locals as the sibling tests do.

The added prose uses the glossary's words. No findings in it.

### Design questions

None open.

Summary:

| Axis | Findings | Blocking | Worst |
|---|---|---|---|
| TASK.md changed | 0 new | 0 | |
| Standards | 0 | 0 | |
| Spec | 0 | 0 | |
| Behaviour | 0 | 0 | |
| Smells | 3 | 0 | R27, `run.py` importing from `commands/task.py` |
| Names | 1 | 1 | R30, `refusal` as a homonym of the glossary's Refusal |

R30 blocks. R27–R29 are Follow-ups. No design questions are open. R8 is deferred.

Verdict: changes needed
