# Review

## Round 1 (reviewing b31a31c)

Reviewed against `TASK.md` as of notes commit 7bb4741 (`wcf-0032: planned`). That commit has a good signature from the identity the planner and the architect share, so it can't be told which of the two made it. The only other commit to touch `TASK.md` is 7f239cd, `Add task wcf-0032`, by the human. No other role changed it. The task has no `DESIGN.md`.

Diff: `git diff 2176c4f...b31a31c`, 24 commits, only files under `tests/`.

### Standards

Nothing breaks design rule 3: no test patches. The only `monkeypatch` calls are `setenv`, `chdir` and setting `git_env`, as the existing tests already did. sbx, ps and gh are reached through stand-ins on `PATH`. Nothing reaches Docker, a sandbox, GitHub or the network. No new helper module was added.

- **R1 · Follow-up.** `tests/test_skills.py:396`: the test stays off the network only because git's `url.<upstream>.insteadOf` matches `skills.github_url(...)` exactly. If the URL the command builds stops matching, git silently clones from github.com, and the test fails offline with a misleading error, or reaches the network online. This would hit whoever changes `skills.github_url`, which is rare. Direction: make a stray clone fail loudly, for example by pointing `https://github.com/` at a path that doesn't exist. Or accept as is.
- **R2 · Follow-up.** Some new docstrings break the project `AGENTS.md` "Writing" rules: sentences under about 25 words, and a reason in its own sentence rather than after a colon. `tests/test_prune.py:28-30` opens with a sentence of about 30 words. `tests/test_repo.py:82-83`, `tests/agent_runtime/test_claude_hooks.py:165-166` and `tests/test_project_tasks.py:119` put their reason after a colon. Existing docstrings use the colon form too. Direction: split the prune docstring. The others can be accepted as is.

### Spec

Checked by hand in a throwaway clone at b31a31c, with `__pycache__` cleared and `PYTHONDONTWRITEBYTECODE=1` before each mutant:

- **Item 3, the `cli.main` tests:** `set_defaults(func=None)` fails a test for create, close, reopen, run, prune, repo check and skills update. Each of these tests compares stdout and stderr together and checks the exit code.
- **pre_push:** removing `case []`, changing `continue` to `break`, and removing `case _` each fail a test.
- **`_is_under`:** `parts[:-1] -> parts[:-2]` fails a test.
- **`create_task`:** changing `or` to `and` fails a test.
- **session_setup:** dropping either `--track` fails a test.
- **config:** emptying each message fails a test. So do mutating the `"none"` fallback or the `", "` join, for projects and for roles, and dropping the config path from `load`'s errors.
- **The turn error:** `known -> None` fails the turn test.
- **Deletions:** each deleted test's mutant still fails another host-tier test at HEAD.

The diff lists only `tests/`. The scope stays inside the task.

- **R3 · Follow-up, accept as is.** TASK.md: "Dropping `--track`, or changing `-c` to `-C`, makes a test fail." `-c -> -C` at `src/agent_runtime/session_setup.py:112` survives. It is an equivalent mutant. That branch runs only once `show-ref` has found no local branch, and then `-C` does what `-c` does, so no test can kill it. TASK.md allows that "the run's results may be wrong". The dev reported it in 9a01731 and in LOG entry 6. The criterion's wording isn't met, so the human may want to confirm this at merge.
- **R4 · Follow-up, accept as is.** TASK.md: "merged into the test just before it (the one about the commit the task's notes get)". The assert went into the create test, not the test that sits just before the deleted one. The parenthesis supports the dev's reading, and the `commit.gpgsign false` mutant fails the merged test.
- **R5 · Follow-up, accept as is.** 60123ce gives `test_variables_read_back_refuse_a_task_id_not_matching_the_pattern` as the test that failed against the lowercasing mutant, and 3db50b4 later deletes that test. At HEAD, `tests/test_task.py::test_task_ids_not_matching_the_pattern_are_refused_as_given` still catches the mutant. Only the commit's stated evidence is out of date. Nothing to do.

### Behaviour

`uv run pytest`, ruff, `ruff format --check` and mypy pass, run as an ordinary user. The host tier takes about 47 s at HEAD, against about 46.5 s at 2176c4f. Each new test passes alone, and the suite passes in reversed order. Mutants of the `_unpushed` fetch, the `is_dir()` check in `_holds_only_an_empty_workspace` and the skills `func=None` each fail their new test. Nothing is left in `/tmp/sbx-agents` or `/tmp/foundry-clone-*`. The prune test kills only its own `sleep`, in a `finally`. The `git config --global` calls write only to the throwaway HOME.

- **R6 · Follow-up.** `tests/test_task_command.py:78-79`: the create/close/reopen test copies `git_env` into the environment. `make_git_env` doesn't clear `GIT_CONFIG_GLOBAL`, so when a developer's shell exports it, the git that `cli.main` runs reads the developer's file and loses the signing key. Reproduced: the test then fails with `fatal: either user.signingkey or gpg.ssh.defaultKeyCommand needs to be configured`. Nothing is written to the developer's file. The existing handoff test fails the same way, so the new test copies an existing pattern. Direction: clear `GIT_CONFIG_GLOBAL` and `XDG_CONFIG_HOME` where `git_env` is copied. Or accept as is.

### Smells

Every function the diff adds or changes:

| Function | Verdict |
|---|---|
| `tests/agent_runtime/test_claude_hooks.py:test_commits_origin_has_but_the_checkout_hasn_t_fetched_count_as_pushed` | new |
| `tests/agent_runtime/test_git_hooks.py:test_a_blank_line_is_skipped_and_the_lines_after_it_still_checked` | new |
| `tests/agent_runtime/test_git_hooks.py:test_a_line_without_a_remote_ref_is_refused_on_its_own` | new |
| `tests/agent_runtime/test_git_hooks.py:test_notes_on_the_task_branch_are_refused_at_any_depth` | clean |
| `tests/agent_runtime/test_session_setup.py:test_both_checkouts_track_their_branch_on_origin_whatever_git_s_config_says` | new |
| `tests/agent_sandbox/test_launcher.py:test_the_summary_says_where_the_github_token_comes_from` | new |
| `tests/test_config.py:test_unknown_project_and_role_are_reported` | clean |
| `tests/test_config.py:test_invalid_shapes` | clean |
| `tests/test_config.py:test_load_s_errors_name_the_config_file` | new |
| `tests/test_github.py:test_a_path_that_is_not_a_file_is_none` | new |
| `tests/test_project_tasks.py:test_a_task_is_its_branch_from_the_default_branch_and_the_template_in_its_task_notes_dir` | clean |
| `tests/test_project_tasks.py:test_a_default_branch_that_is_not_a_branch_is_refused_and_nothing_is_pushed` | new |
| `tests/test_prune.py:test_prune_prints_what_it_killed_or_an_error_and_exits_accordingly` | new, R8 |
| `tests/test_repo.py:test_check_prints_each_project_s_result_and_exits_1_unless_all_conform` | new, R8, R9 |
| `tests/test_run.py:test_run_prints_the_turn_and_the_new_session_then_hands_over_to_the_launcher` | new, R7, R8 |
| `tests/test_run.py:test_a_turn_that_names_no_role_is_refused_naming_the_turn_file` | clean |
| `tests/test_session.py:test_a_file_where_the_session_directory_goes_is_refused` | new |
| `tests/test_skills.py:test_skills_update_exits_0_when_clean_and_1_with_the_conflicts_on_stderr` | new |
| `tests/test_task_command.py:test_create_close_and_reopen_print_what_they_did_or_an_error_and_exit_accordingly` | new, R7 |
| the deleted tests | clean |

- **R7 · Follow-up, possible Duplicated Code.** `tests/test_task_command.py:66-79` repeats the setup that the list test (`:206-220`) and the handoff test (`:303-324`) already share. Each makes `config/`, writes a `foundry.yaml` whose `store` project points at `project_repository.path`, calls `chdir`, and copies `git_env`. That makes three copies in the file. `tests/test_run.py:109-120` has a fourth that also copies `git_env`. Whoever next changes `foundry.yaml`'s shape or `git_env` edits every copy. *Reviewer's note:* the sub-agent labelled this Blocking. It is downgraded because TASK.md says to use the fixtures in `tests/support/` and `conftest.py` "rather than new helpers", and the three copies differ: one writes a task template, another writes a second project. The diff extends an existing pattern. Direction: if this is taken up, one foundry-over-`project_repository` fixture in that file, in a later task.
- **R8 · Follow-up, possible Duplicated Code.** `tests/test_prune.py:32-39`, `tests/test_run.py:112-117` and `tests/test_repo.py:108-112` each write a `#!/bin/sh` stand-in, `chmod` it and put it first on `PATH`. The prune and run tests write the same `sbx` script. `tests/support/machine.py:34` `stand_in` already has this shape, but it takes only an exit code. Direction: give `stand_in` a script body rather than adding a helper.
- **R9 · Follow-up, possible Long Function.** `tests/test_repo.py:79-113` does three jobs: it writes a foundry with the repo policy, compiles an endpoint-to-response dict into a shell `case` (`json.dumps(..., default=bytes.decode)` quietly turns base64 bytes into text, `:105`), and runs the command. Direction: move the gh stand-in into a small named function in that file.

### Names

Every name the diff adds or changes is clean, judged at its uses, except for one prose word. That includes the 15 new or changed test names, `github_line`, `config_path`, `refs_before`, `stand_ins`, `sleeping`, `CI_GATE`, `CODEOWNERS`, `responses`, `cases`, `gh`, `ssh_key_path`, `session_path`, `second`, `third` and `error`. `session_path` names a file standing where the session dir would go, so naming it for that role is justified. The create test that took the signing assert still reads true.

- **R10 · Blocking.** `tests/test_repo.py:82` and `tests/test_task_command.py:69`: the new docstrings say "in a foundry instance of its own". GLOSSARY.md, under **Foundry**, lists "instance" under _Avoid_. The same diff gets it right in `tests/test_skills.py:394`: "in a foundry of its own". The phrase already appears in `src/foundry/paths.py`, `pruning.py` and the existing list and handoff test docstrings in `tests/test_task_command.py`. That is drift, not agreement, and the new lines copy it. The next reader of these tests meets two words for one thing. Direction: write "in a foundry of its own" in the two new docstrings, and list the existing uses as a follow-up.

### Summary

Findings: Standards 2 (none block; worst R1, the network guard depends on an exact URL match). Spec 3 (none block; worst R3, the `-c -> -C` mutant is equivalent, so the criterion's wording can't be met). Behaviour 1 (does not block; R6, an inherited `GIT_CONFIG_GLOBAL`). Smells 3 (none block, one downgraded; worst R7, duplicated foundry setup). Names 1, Blocking (R10, "foundry instance"). No design questions.

Verdict: changes needed

## Round 2 (reviewing 7dd5591)

Reviewed against `TASK.md` as of notes commit 7bb4741, as in round 1. No commit has touched `TASK.md` since. 7bb4741 has a good signature from the identity the planner and the architect share, so it can't be told which of the two made it. The task has no `DESIGN.md`.

Fix diff: `git diff b31a31c...7dd5591`, three commits (2bb57d4, 83edc51, 7dd5591), all under `tests/`. `uv run pytest`, ruff, `ruff format --check` and mypy pass at 7dd5591. The host tier takes about 48 s.

### Earlier findings

- **R1 · closed.** Fixed in 7dd5591. `tests/test_skills.py:398` sends every other `https://github.com/` URL to a `no-github` path that doesn't exist. git uses the longest insteadOf prefix that matches, so the skill's own URL still reaches the local upstream (`:397`). Checked in a throwaway clone by making the specific rule miss. The fetch then fails on `.../no-github/mattpocock/skills.git`, with no network. The rule is written only to the throwaway global config that `git_identity` sets up.
- **R2 · closed.** The prune docstring is split in 83edc51 (`tests/test_prune.py:28-30`). The colon form in the other three was accepted as is.
- **R3, R4, R5 · accepted as is**, as in round 1. R3 is still for the human at merge.
- **R6, R7, R8, R9 · deferred.** The dev's reasons hold. R6's fix belongs in `make_git_env` in `tests/support/`. TASK.md asks for existing helpers rather than new ones (R7). R8 and R9 are refactors of shared stand-in helpers. All four are left to a later task.
- **R10 · closed.** Fixed in 2bb57d4. No line the task diff adds calls a foundry an "instance". The older uses in `src/foundry/paths.py`, `src/foundry/agent_sandbox/pruning.py` and the list and handoff docstrings in `tests/test_task_command.py` stay as a suggested follow-up.

### Standards

No new findings. The new docstring at `tests/test_skills.py:394-396` gives its reason with "so", in sentences under 25 words. The new config line is git configuration, not a patch, so design rule 3 holds.

### Spec

No new findings. Only `tests/` changed. Each fix commit makes one change and says why. In a throwaway clone, `set_defaults(func=None)` in `src/foundry/commands/skills.py` still fails the skills update test. That test still asserts exit 0 and stdout for a clean update, and exit 1 with the conflict on stderr for a conflicted one.

### Behaviour

No new findings. The skills update test passes on its own, in its file and beside `tests/test_task_command.py`. Run outside the suite with git 2.53.0 and the same two rules:
- the skill's URL goes to the upstream;
- any other `https://github.com/` URL, with or without `.git`, fails on the missing path.

The conflicted half's fetch still reaches the local upstream. The real `~/.gitconfig` is untouched.

### Smells

| Function | Verdict |
|---|---|
| `tests/test_prune.py:test_prune_prints_what_it_killed_or_an_error_and_exits_accordingly` | clean (docstring only) |
| `tests/test_repo.py:test_check_prints_each_project_s_result_and_exits_1_unless_all_conform` | clean (docstring only; R9 unchanged) |
| `tests/test_task_command.py:test_create_close_and_reopen_print_what_they_did_or_an_error_and_exit_accordingly` | clean (docstring only; R7 unchanged) |
| `tests/test_skills.py:test_skills_update_exits_0_when_clean_and_1_with_the_conflicts_on_stderr` | clean |

No new findings.

### Names

The one new name, the path segment `no-github` (`tests/test_skills.py:398`), is clean. The added prose uses the glossary's words: "foundry", "sandbox", "upstream" in its Skill sense, and the code's "ssh-agent". No new findings.

### Summary

Findings: Standards 0. Spec 0. Behaviour 0. Smells 0. Names 0. None block. No design questions. R1, R2 and R10 are closed. R6–R9 are deferred, and R3–R5 accepted as is.

Verdict: approved
