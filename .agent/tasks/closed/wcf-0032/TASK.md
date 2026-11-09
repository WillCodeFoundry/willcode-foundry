# Task wcf-0032: Tighten the host-tier tests from a mutation-testing run

## Goal
A mutation-testing run (mutmut 3.8.1 over `src/`, host tier only, made by another agent) found host-tier tests that are redundant, tests that assert too little for a mutant to fail them, and code no test reaches. Each behaviour should be tested once, at the cheapest tier that catches its bug (CONTRIBUTING.md, "Test tiers"). So: delete the redundant tests, strengthen the weak ones and add tests for the uncovered code. Only tests change. The run's results may be wrong, so check every change by hand against a mutant before making it.

## Acceptance criteria
Method, for every item below:
- [ ] **Deletion:** before deleting, the dev breaks by hand the code the test covers, with the test deselected, and at least one other host-tier test fails. The commit message names the mutation and the test that failed. If no other test fails, the test stays and is reported at the end as kept.
- [ ] **New or stronger test:** written test-first. It fails against the mutant described in its item and passes against the real code. The commit message names the mutant.
- [ ] One commit per item, its message saying why. Before every commit, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy` pass (after `uv sync --group dev`).
- [ ] `git diff --stat origin/main...HEAD` lists only files under `tests/`.
- [ ] No new test in the host tier needs Docker, a real sandbox, GitHub or the network. Tests never patch (ARCHITECTURE.md design rule 3). A stand-in executable on `PATH` is allowed.
- [ ] If a new test exposes a real bug in `src/`, the dev doesn't fix it. They stop, end the turn as `stuck` and report the bug, naming the test and the failing behaviour.

1. Delete:
- [ ] `tests/test_paths.py`: `test_paths_are_built_without_touching_the_filesystem`.
- [ ] `tests/test_run.py`: `test_an_uppercase_task_id_is_refused_not_lowercased`. `test_an_uppercase_id_is_refused_not_lowercased_and_nothing_is_pushed` in `tests/test_project_tasks.py` covers the lowercasing, and `run` only passes the id through.
- [ ] `tests/test_run.py`: `test_the_runtime_is_built_into_the_kit`. `test_a_failed_build_aborts_the_launch` and `tests/test_runtime_build.py` cover it.
- [ ] `tests/test_run.py`: `test_a_task_that_doesn_t_exist_is_refused`. This was found only by reading, so it needs the hand check like the others.
- [ ] `test_the_tasks_notes_commit_is_signed_with_your_signing_key` in `tests/test_project_tasks.py` is merged into the test just before it (the one about the commit the task's notes get), as one more assert. The test of its own is gone.
- [ ] Judged, deleted only if the evidence holds, the reason recorded in `LOG.md`:
  - `tests/test_session.py`: `test_variables_read_back_refuse_a_task_id_not_matching_the_pattern`. Keep it if `SessionVariables.from_env` could build a task id without going through `Task`.
  - `tests/test_prune.py`: `test_prune_is_a_command`, which overlaps `test_the_readme_lists_exactly_foundrys_commands` in `tests/test_docs.py`.

2. Strengthen:
- [ ] `tests/test_config.py` `test_invalid_shapes`: each case matches its error message, not a bare `pytest.raises(FoundryError)`. Emptying any one message makes the test fail.
- [ ] `tests/test_config.py` `test_unknown_project_and_role_are_reported` gains a case with zero roles and one with several. Mutating the "none" fallback, or the `", "` join, makes it fail.
- [ ] A test asserts that `config.load`'s errors name the config file's path.
- [ ] `tests/test_run.py` `test_a_turn_that_names_no_role_is_refused_naming_the_turn_file` checks the known roles in the message. The mutation `known -> None` makes it fail.

3. Add tests:
- [ ] `commands/task.py` `create_main`, `close_main` and `reopen_main`; `commands/run.py` `main`; `commands/repo.py` `check_main`; and `commands/prune.py` `main` are each tested end to end through `cli.main`, asserting stdout, stderr and the exit code, as the `cli.main` tests in `tests/test_task_command.py` do. For create, close, reopen and run, the mutation `set_defaults(func=None)` makes a test fail. Any part that needs a real sandbox or GitHub is left to the docker or sbx tier, and listed at the end.
- [ ] `agent_runtime.git_hooks.pre_push`: a blank stdin line followed by a ref that must be refused, and a malformed line, which is refused on its own. Removing `case []`, removing `case _`, or changing `continue` to `break` makes a test fail.
- [ ] `agent_runtime.git_hooks._is_under`: a file whose immediate parent is the root. The mutation `parts[:-1] -> parts[:-2]` makes it fail.
- [ ] `project_tasks.create_task`: a default branch that isn't among the branches. Changing that `or` to `and` makes it fail.
- [ ] `agent_runtime.session_setup`: the task branch and the notes worktree each track their upstream. Dropping `--track`, or changing `-c` to `-C`, makes a test fail.
- [ ] `github.GhCli.file_text`: the branch where the path is not a file.
- [ ] `agent_sandbox.launcher.launch_summary`: the line with a token, and the line without one.
- [ ] `session._holds_only_an_empty_workspace`: the session path is a file.
- [ ] `commands/skills.py` `update_main`, through `cli.main`: a clean update exits 0, and a conflicted one exits non-zero, with the conflict message on stderr. If `skills.update` can't run without GitHub, it is pointed at a local upstream repository, or skipped and listed as another tier's.
- [ ] `agent_runtime.claude_hooks._unpushed`: the `git fetch origin <branch>` it makes. If `tests/agent_kit/test_stop_hook.py` already shows this (that folder was left out of the run), no test is added and that is reported.

At the end, the dev's last `LOG.md` entry lists what was deleted, strengthened and added; what was judged and kept, and why; and what was skipped as belonging to another tier.

## Out of scope
- Any change under `src/`, including fixing a bug a test exposes.
- Mutants in help text, descriptions or message wording; the `--quiet` and flush flags; the case of git config keys; the `su`/`sudo` arguments in the modelled-machine fakes (the docker tier covers the real commands).
- Anything under `tests/agent_kit/`, or `agent_runtime.session_init`, which the run couldn't mutate.
- Adding mutmut, or any other dependency, to `pyproject.toml`. Rerunning mutmut is optional, and only in a throwaway clone.
- Tests for code the run didn't list.

## Context
- Start from `main` at or after 2176c4f (PR #46, wcf-0031). wcf-0031 moved tests from `tests/test_task.py` into `tests/test_project_tasks.py` and `tests/test_task_command.py`. Find each test by name, not by file or line.
- `CONTRIBUTING.md`: "Test tiers", and the check commands. `ARCHITECTURE.md`: "Design rules", rule 3.
- `tests/support/` (`project_repository.py`, `machine.py`, `kit.py`) and the fixtures in `tests/conftest.py` (`project_repository`, `git_env`): real git repositories in temporary folders. Use these rather than new helpers.
- `tests/test_task_command.py`: the existing tests through `cli.main` are the pattern for item 3's end-to-end tests.
- `tests/agent_runtime/test_git_hooks.py`, `test_session_setup.py` and `test_claude_hooks.py` hold the `agent_runtime` tests that item 3 extends.
- `SessionVariables.from_env` (`src/foundry/session.py`) currently builds the task with `Task.as_open`.
- `commands/run.py` `main` never returns: it ends in `agent_sandbox.launch`.
- The host tier takes about 20 seconds. Keep it that order of magnitude.

## Seams to test
- `cli.main(argv)`, through its exit code, stdout and stderr: that each command is wired to its handler and reports what it did.
- `config.load`: the message of each config error, including the path.
- `require_open_task_and_role` (`commands/run.py`): the turn error's message names the known roles.
- `ProjectTasks.create_task`, against a real repository from `project_repository`: the default-branch check.
- `git_hooks.pre_push(refs, session)` and `_is_under`: which refs and paths are refused.
- `session_setup`, against real git: the upstream each checkout tracks.
- `GhCli.file_text`, `launch_summary`, `_holds_only_an_empty_workspace`, `skills.update_main`, `claude_hooks._unpushed`: the branches listed in item 3.

## Terms and decisions
- None.

## Open questions
- None.
