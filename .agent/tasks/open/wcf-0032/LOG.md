# Log

## 1 · planner · planned
Done: TASK.md drafted with the human from a mutation-testing report and approved; checked against the code on main at 2176c4f and against checklist.md.
Next: dev starts with item 1 (deletions), checking each by hand against a mutant as TASK.md says.
- The human chose to keep the whole report (deletions, strengthened tests and new tests) in one task rather than split it in three, so it may take the dev more than one session.
- Corrections made to the report: `Session.from_env` is `SessionVariables.from_env`; `skills.update_main` has no exit code 2, so its item tests 0 on success and non-zero on a conflict (the human's answer).
- No change to structure, so `planned`, not `needs-design`.

## 2 · dev · progress
Done: merged origin/main (already up to date at 2176c4f); host tier passes (~45 s here).
Next: one commit per TASK.md item, in its order: item 1 deletions (each hand-checked against a mutant with the test deselected), then item 2 strengthenings, then item 3 new tests, each test-first against its named mutant. Then a draft PR, CI, and `ready-for-review`.

## 3 · dev · progress
Done: item 1, each deletion hand-checked with the test deselected; the mutants and the tests that failed are in each commit message.
- Deleted `test_paths_are_built_without_touching_the_filesystem` (1da7f07), `test_an_uppercase_task_id_is_refused_not_lowercased` (60123ce), `test_the_runtime_is_built_into_the_kit` (1899fcd), `test_a_task_that_doesn_t_exist_is_refused` (fdd65d1).
- Merged `test_the_tasks_notes_commit_is_signed_with_your_signing_key` into `test_a_task_is_its_branch_from_the_default_branch_and_the_template_in_its_task_notes_dir` (a9a4f6b). The test physically just before it was the orphan test, but TASK.md describes "the one about the commit the task's notes get", which is the create test (it checks the commit's parent). Mutant `commit.gpgsign false` fails it.
- Judged and deleted `test_variables_read_back_refuse_a_task_id_not_matching_the_pattern` (3db50b4): `from_env` builds the task with `Task.as_open`, so it can't build one without going through `Task`. Both mutants of Task's check fail other tests. A hand-made mutant that lowercases in `from_env` fails no other test, but is still refused by from_env's read-back check, only with another message.
- Judged `test_prune_is_a_command`: kept for now. With it deselected, `set_defaults(func=None)` in `prune.py` fails no test; the docs test checks only the command's name. To judge again once item 3's end-to-end prune test exists.
Next: item 2, strengthen `test_config.py` and the turn test in `test_run.py`.
