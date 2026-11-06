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

## 4 · dev · progress
Done: item 2, each test checked against its named mutants (in the commit messages).
- `test_invalid_shapes` matches each whole message (942ebf5).
- `test_unknown_project_and_role_are_reported` runs with none, one and several names, for projects and roles (d268615).
- New `test_load_s_errors_name_the_config_file` (4218c68).
- The turn test matches the known roles; fails on `known -> None` (524ea22).
Next: item 3, starting with the end-to-end `cli.main` tests, then judge `test_prune_is_a_command` again.

## 5 · dev · progress
Done: item 3's first bullet, end-to-end tests through `cli.main`, one commit per command (each names its mutants):
- task create, close, reopen (9f2a560); `foundry run` up to the launcher's first check, the missing SSH key (a7f5263); prune (86e327b); repo check (8c9632d).
- The run and prune tests put stand-ins for `sbx` and `ps` on PATH. The launcher and prune both prune ssh-agents, and a real `ps` would let a test kill a developer's own.
- Left to the sbx tier: what `run` does after the launcher's first check (ssh-agent, sandbox, attach).
- `test_prune_is_a_command` judged again and deleted (ca99a65): the new prune test now catches `set_defaults(func=None)`.
Next: the rest of item 3, from `git_hooks.pre_push`.

## 6 · dev · ready-for-review
Done: every TASK.md item, each commit naming its mutants and, for a deletion, the test that failed. Item 3's first bullet is one commit per command. Main merged (already up to date). Host tier, ruff, ruff format and mypy pass. The host tier takes ~49 s here, against ~45 s before. `git diff --stat origin/main...HEAD` lists only `tests/`. Draft PR: https://github.com/WillCodeFoundry/willcode-foundry/pull/50, and its CI passes.
- [x] Each deletion hand-checked with the test deselected; each new or stronger test fails against its mutants.
- [x] One commit per item, with the checks passing before each; only `tests/` changed.
- [x] No Docker, sandbox, GitHub or network in the new tests, and no patching. They use stand-in `sbx`, `ps` and `gh` executables on PATH, and git's `url.<base>.insteadOf`.
- [x] No new test exposed a `src/` bug that needed a stop (two oddities are listed under Next).

Deleted:
- `test_paths_are_built_without_touching_the_filesystem` (1da7f07)
- `test_an_uppercase_task_id_is_refused_not_lowercased` (60123ce)
- `test_the_runtime_is_built_into_the_kit` (1899fcd)
- `test_a_task_that_doesn_t_exist_is_refused` (fdd65d1)
- `test_the_tasks_notes_commit_is_signed_with_your_signing_key`, merged as one assert into the create test (a9a4f6b). TASK.md describes "the one about the commit the task's notes get", which is the create test, not the orphan test that sits just before it.
- Judged, deleted: `test_variables_read_back_refuse_a_task_id_not_matching_the_pattern` (3db50b4). `from_env` builds the task only through `Task.as_open`, and other tests catch both mutants of Task's check.
- Judged, deleted: `test_prune_is_a_command` (ca99a65), once the end-to-end prune test caught `func=None`. Before that test, no other test caught it, so it had been kept.

Strengthened: `test_invalid_shapes` (942ebf5); `test_unknown_project_and_role_are_reported` (d268615); new `test_load_s_errors_name_the_config_file` (4218c68); the known roles in the turn test (524ea22).

Added:
- Through `cli.main`: task create/close/reopen (9f2a560), run (a7f5263), prune (86e327b), repo check (8c9632d), skills update (b397398).
- `pre_push` with a blank and a malformed line (498ed65); `_is_under` for a file whose parent is the root (30cb21e); `create_task` with a default that isn't a branch (b47828d); session_setup's upstreams (9a01731); `GhCli.file_text` for a folder or link (4d2b481); the github line of `launch_summary` (166f3ed); a file as the session path (9bb439a); the fetch in `_unpushed` (b31a31c).
- `tests/agent_kit/test_stop_hook.py` didn't show the fetch: it passes with the fetch removed, so a test was added.

Mutants that survive, judged equivalent:
- `switch -c` -> `-C` in session_setup. That line runs only when the local branch doesn't exist, where `-C` does what `-c` does.
- Dropping `--track` changes nothing under git's default `branch.autoSetupMerge`. The test sets it to false, so dropping either `--track` fails it.

Left to other tiers:
- Everything `foundry run` does after the launcher's first check (ssh-agent, sandbox, attach) belongs to the sbx tier. The test stops at the missing SSH key.
- `repo check --fix` is not run through `cli.main`. With the test's empty rulesets it prints the same as a check, and `tests/test_repo_policy.py` covers `fix_project`.

For the reviewer: the run and prune tests stand in for `ps` as well as `sbx`. With the real `ps`, prune would kill a developer's own foundry ssh-agents.

Next (suggested follow-ups, out of scope):
- When the default branch isn't a branch (a HEAD on a tag), `create_task` says "the repository has no commits to branch … from", though the repository has commits.
- `ProjectClone.default_branch` returns `"ref: refs/tags/v1"` for a HEAD on a tag, since it strips only `refs/heads/`.

## 7 · reviewer · changes-needed
Done: review round 1 of b31a31c, in REVIEW.md. TASK.md was changed only by allowed commits: 7f239cd by the human, and 7bb4741 by the identity the planner and the architect share. The task has no DESIGN.md. Every mutant TASK.md names was checked by hand in a throwaway clone, and each fails a test except `-c -> -C`, which is equivalent (R3). Checks pass, and the host tier takes about 47 s.
Next: the dev fixes R10, the one Blocking finding: "foundry instance" in two new docstrings, where GLOSSARY.md avoids "instance". R1–R9 are follow-ups. Answer each by its id, as a fix or as a reason to leave it. R3, R4 and R5 are accepted as is, so they need no answer.
- For the human, at merge: R3. TASK.md's "changing `-c` to `-C` makes a test fail" can't be met, since that mutant is equivalent.
