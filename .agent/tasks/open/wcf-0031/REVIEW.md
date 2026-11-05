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

- **R15 (Follow-up).** `src/foundry/project_tasks.py:137-140`, the `handoff` docstring. Its second paragraph has six sentences, against "paragraphs to three sentences" in `AGENTS.md` "Writing". It also lists five refusals in running prose, against "Use a table or a list for anything shaped like one". Whoever needs to know what `handoff` refuses meets it on every read. Direction: put the refusals in a short list, apart from what it writes.
- **R16 (Follow-up).** `src/foundry/project_tasks.py:5`, the module docstring, still says "Callers pass task ids, and get Tasks back", but `handoff` returns `None`. The harm is small. Direction: soften the sentence, or accept as is.

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

- **R17 (Follow-up).** "refused … before the repository is read" (ROLE, note, task id) holds only by the order of lines in `handoff_main` (`src/foundry/commands/task.py:112-115`). The end-to-end test checks only that nothing was pushed, so moving `require_valid_handoff_args` inside the `with` would still pass. It is a Follow-up, not Blocking: round 1 accepted the same shape, and `TASK.md`'s seam asks for the check "called with plain values and the config", which it is. Direction: accept as is, since design rule 7's composition root is read in place.
- **R18 (Follow-up).** "the task … is both open and closed (the messages `get_task_by_id` gives)" has no `handoff` case. Only `get_task_by_id`'s own test covers it. `handoff` calls `get_task_by_id` first, so this is shown by reading the code. Direction: accept as is, or add the case to `test_handoff_refuses_and_pushes_nothing`.

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

- **R19 (Follow-up), possible Duplicated Code.** `tests/support/project_repository.py:53` (`project_tasks_of`) and `:86` (`ProjectRepository.project_tasks`) each build `ProjectTasks(<clone>, "store")`, with the project name spelled twice. The sub-agent labelled it Blocking. It is downgraded here because mypy flags both sites when the constructor changes, as a49fc8c did, so only the literal can drift. That name appears only in hint messages, which tests match by pattern. Direction: have one build through the other, or name the project once.

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
| Standards | 2 | 0 | R15, `handoff`'s docstring |
| Spec | 2 | 0 | R17, the order of checks is shown only by reading |
| Behaviour | 0 | 0 | |
| Smells | 1 | 0 | R19, the duplicated `"store"` build |
| Names | 1 | 1 | R20, `head()` for agent-notes |

No design questions are open.

Verdict: changes needed
