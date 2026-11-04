# Log

## 1 · planner · progress
Done: settled the task with the human in two rounds: one id pattern, `[a-z]+-[0-9]{4,}`, enforced
by `Task`; no lowercasing anywhere, not even at creation; a message that explains the pattern;
`Task.from_id_and_status` removed; README and glossary updated; no ADR. TASK.md approved and written.
Next: hand to the dev.

## 2 · planner · planned
Done: TASK.md approved and pushed. No new module, seam or shared interface, so no design needed.
Next: dev starts from TASK.md. Note the many test fixtures that use ids the pattern refuses, listed
under Context, including the docker and sbx tiers.

## 3 · dev · progress
Done: merged origin/HEAD (already up to date); read TASK.md, the notes and the project docs.
Next, test-first:
1. `Task`: tests for the accepted and refused ids and the exact message; then `_TASK_ID` becomes
   `[a-z]+-[0-9]{4,}`, `from_id_and_status` goes, `as_open`/`as_closed` build `Task` directly.
2. `ProjectTasks` create/close/reopen/get given `WCF-0042`: refused, nothing pushed (was: lowercased).
3. `SessionVariables.from_env` given `AGENT_TASK=WCF-0042`: refused.
4. Move every test fixture to valid ids (`t1` → `tst-0001`, `WCF-0042` → `wcf-0042`, …),
   including the docker tier and `sbx-smoke` → `sbx-0001` (with CONTRIBUTING.md's mention of it).
5. README.md and GLOSSARY.md.

## 4 · dev · ready-for-review
Done: every acceptance criterion, in d416647 (code and tests) and df53ba3 (docs). Draft PR:
https://github.com/WillCodeFoundry/willcode-foundry/pull/45. Its CI passes, sandbox-image (docker
tier) included. Host tier, ruff and mypy pass here.
- [x] `Task`, `as_open`, `as_closed` accept exactly `[a-z]+-[0-9]{4,}`: `test_valid_task_ids_are_kept_as_given`.
- [x] Every listed refused id raises `FoundryError`, plus `wcf-0042\n` and Arabic-Indic digits:
      `test_task_ids_not_matching_the_pattern_are_refused_as_given`, which checks the exact message.
- [x] No lowercasing under `src/foundry/` but `session._slug`, which is out of scope. create, close,
      reopen and get given an uppercase id are refused with no ref changed on origin
      (`test_an_uppercase_id_is_refused_not_lowercased_and_nothing_is_pushed`); `foundry run`'s
      `require_open_task_and_role` too (`test_run.py`).
- [x] `SessionVariables.from_env` with `AGENT_TASK=WCF-0042` refused (`test_session.py`).
- [x] `Task.from_id_and_status` removed.
- [x] README.md and GLOSSARY.md state the pattern; `tests/test_docs.py` passes.
- [x] Host tier, ruff, mypy pass.
Notes for the reviewer:
- Fixtures moved to `tst-0000`/`tst-0001`/… and `cls-0000` (was `t0`/`t1`/`c0`); see NAMES.md.
- The sbx tier's task `sbx-smoke` is now `sbx-0001`, with CONTRIBUTING.md to match. The human must
  create it once (`uv run foundry task create foundry-test sbx-0001`) before running `-m sbx`; the
  sbx tier was not run here.
- `test_session.py`'s slug-collision case now collides on the project name, since valid task ids can
  no longer make two tasks' slugs collide (LEARNINGS.md).
Next: the reviewer's round.
