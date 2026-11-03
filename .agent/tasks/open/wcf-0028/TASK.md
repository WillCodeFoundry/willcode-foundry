# Task wcf-0028: List a project's tasks and whose turn each is

## Goal
Today the only way to see what is waiting on you is to read `TURN` in every
task's notes dir on `agent-notes`, project by project. Add `foundry task list`,
which prints every open task in the configured projects with whose turn it
is, so you can see at a glance which tasks wait for you and which role to run
next.

## Acceptance criteria
- [ ] `foundry task list` prints, on stdout, one line per open task across
      every project in `config/foundry.yaml`: project, task id and the
      stripped text of its `TURN` file, in aligned columns two spaces apart,
      the widths taken across all the task lines printed. Projects are in name
      order and tasks in id order within each.
- [ ] `foundry task list PROJECT [PROJECT ...]` lists only the projects named,
      in name order, a name given twice listed once. A name not in
      `config/foundry.yaml` is refused before anything is listed, with the
      same message as `foundry task create` gives, and exit 1.
- [ ] `--turn ROLE` lists only the tasks whose `TURN` equals `ROLE` exactly:
      `--turn human` those waiting for you, `--turn dev` those for the dev.
      Any value is accepted, as `TURN` can hold any line.
- [ ] Closed tasks (under `.agent/tasks/closed/`) are never listed.
- [ ] A project with no open tasks prints `PROJECT  no open tasks` on stdout,
      outside the aligned columns. That includes a project whose
      `.agent/tasks/open/` is gone because its last task was closed. With
      `--turn ROLE`, a project with open tasks but none matching prints
      `PROJECT  no open tasks with turn ROLE` instead.
- [ ] A project is a failure, and nothing of it is listed, when any of these
      holds: its repository can't be reached; it has no `agent-notes` branch;
      an open task's `TURN` is missing, empty or not a file; a directory under
      `.agent/tasks/open/` is not a valid task id. It prints `error: PROJECT:
      <message>` on stderr, the remaining projects are still listed, and the
      command exits 1. A message about a task names it and says how to fix it;
      one about the branch names `agent-notes`. Otherwise the command exits 0,
      whether or not any task was listed.
- [ ] Entries under `.agent/tasks/open/` that aren't directories are ignored.
- [ ] Listing reads only: it makes no commit and no push, and needs no signing
      key.
- [ ] Listing and reading `TURN` go through git objects on the fetched
      `agent-notes`, never the checked-out files: a `TURN` that is a symlink
      shows the link's target name as its turn, and nothing outside the clone
      is read.
- [ ] Each project costs one fetch of `agent-notes`, however many tasks it
      has.
- [ ] The README's command table lists `foundry task list [PROJECT ...]`, so
      `tests/test_docs.py` passes; the README paragraph on `TURN` and
      `ARCHITECTURE.md`'s codemap rows for `project_tasks.py` and
      `project_clone.py` mention listing.
- [ ] The host tier, ruff and mypy pass.

## Out of scope
- How long a task has waited. `LOG.md` entries carry no date, and the scratch
  clone fetches one commit deep, so this needs its own task.
- The task's pull request, its CI state, or open `Asks` ids: that is
  `foundry task show`, a later task.
- Machine-readable output (`--json`).
- Listing closed tasks.
- Running anything: `task list` never starts a sandbox or changes `TURN`.
- Flagging a `TURN` that names a role not in `config/foundry.yaml`;
  `foundry run` already refuses it.
- Changing `ProjectClone.read`, `read_task_turn` or `in_scratch_clone`; add
  methods beside them.
- Changing how `foundry repo check` prints its errors.
- Creating a missing `agent-notes` branch: `foundry task create` does that.
- Keeping `.agent/tasks/open/` in git when its last task closes.

## Context
- `src/foundry/commands/task.py`: add `list` beside `create`, `close` and
  `reopen`, with its own parser (optional `PROJECT`s via `nargs="*"`, and
  `--turn`): the shared `task_arguments` make PROJECT and TASK required. Update
  the `task` help text and the module docstring. Its `main` is a composition
  root that only builds and passes (design rule 7 in `ARCHITECTURE.md`). The
  printed lines come from a pure function the tests call, named apart from the
  existing `report`: it takes each project's summaries or error and the
  `--turn` filter, and returns the stdout lines and the stderr lines; `main`
  prints them and exits 1 if there are stderr lines.
- Errors: `cli.main` prints raised `FoundryError` and `GitError` as
  `error: <message>` on stderr and exits 1 (design rule 6). Listing does the
  same per project and carries on, so a project's failure is a value passed to
  the printing function, not an exception reaching `cli.main`.
  `src/foundry/commands/repo.py` is the pattern for the loop and the exit
  code, but it prints its errors on stdout, inside its report; do not copy
  that.
- `src/foundry/project_tasks.py`: `ProjectTasks` finds tasks one id at a time
  (`get_task_by_id`) and reads a turn (`read_task_turn`, which raises on a
  missing or empty `TURN`). Each call checks out and fetches again, so looping
  them costs a fetch per task. Add `TaskSummary`, a frozen dataclass of a
  `Task` and its turn text, and
  `ProjectTasks.list_open_task_summaries() -> list[TaskSummary]`: the open
  tasks only, in id order. It fetches `NOTES_BRANCH` once; returns an empty
  list when `local_list_dir` of `OPEN_DIR` raises the missing-path error (git
  keeps no empty dir, so `open/` is gone once its last task closes), catching
  only that class, as `create_task` catches only `TaskNotFoundError`; builds
  each `Task` with `Task.as_open`; and raises `FoundryError` for a missing or
  empty `TURN`, wording shared with `read_task_turn`, not copied. Names are
  suggestions; the dev records the final ones in `NAMES.md`.
- `src/foundry/project_clone.py`: `ProjectClone` reads files from git
  (`read`, which refetches on every call) and checks paths (`exists`, on the
  checked-out files), but can't list a dir's entries. Add, beside them:
  `fetch_branch(branch)`, which raises `FoundryError` when the remote has no
  such branch; then `local_list_dir(branch, path)` and `local_read(branch,
  path)`, which make no network call, read git objects (`ls-tree`, `show`) as
  `read` does, and raise `FoundryError` when the branch isn't fetched.
  `local_list_dir` lists only tree entries, so stray files and symlinks are
  not task dirs, and raises, for a missing dir, a subclass of `FoundryError`
  that nothing else raises, so a caller can catch it without also catching an
  unfetched branch. `local_read` raises when the file is missing or not a
  file.
- `src/foundry/task.py`: the one place `OPEN_DIR`, `TURN_FILE` and
  `NOTES_BRANCH` are spelled (design rule 1). Use them; spell no path again.
- `config.Config.project` raises the unknown-project error `create` gives.
- `README.md`: the command table, and the paragraph on `TURN`.
- `tests/test_task.py`: real repositories in temporary folders (`origin_dir`,
  `git_env`); tests never patch (design rule 3).
- No new dependencies.

## Seams to test
- `ProjectTasks.list_open_task_summaries` against a real repository in a
  temporary folder, as `tests/test_task.py` does: which tasks are open and
  their turns; closed tasks and stray files left out; a symlinked `TURN`; no
  open dir after the last task closed; and each failure: missing, empty and
  directory `TURN`, an invalid-id dir, no `agent-notes` branch, an
  unreachable repository. Catches reading the wrong dir or branch, following
  links, and failing where it should list.
- `ProjectClone`'s `fetch_branch`, `local_list_dir` and `local_read`, on a
  fetched and an unfetched branch: a missing dir raises the narrow error and
  an unfetched branch raises something else. Catches a call that reaches the
  network, that quietly returns nothing for what is missing, or whose error
  is too broad to catch safely.
- The fetch count: a repository with several tasks, run with a counting
  stand-in for git on `PATH`. Catches a fetch per task.
- The function that turns each project's summaries, or its error, into
  stdout and stderr lines, called with plain values: the filter, the column
  widths, the two no-tasks lines, the error line. Catches formatting and
  filtering bugs without git.
- The parser: `task list` takes optional projects and `--turn`, as
  `test_create_takes_a_project_and_a_task` checks `create`; and an unknown
  project is refused before any listing.

## Terms and decisions
- None. `TaskSummary` is a code-level name; Turn is already in GLOSSARY.md.

## Open questions
- None.
