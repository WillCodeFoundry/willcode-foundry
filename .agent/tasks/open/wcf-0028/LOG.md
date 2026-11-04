# Log

## 1 · planner · planned
Done: TASK.md written and approved by the human. Outcome `planned`: the work
adds methods to `ProjectClone` and `ProjectTasks` and a `TaskSummary` value
type, within those modules' stated jobs; no new module, seam, rule or ADR.
Next (dev): start from TASK.md's "Context". Suggested follow-ups, not part of
this task:
- `foundry repo check` prints per-project errors on stdout, inside its report;
  `task list` prints them as `error: ...` on stderr. Consider making `repo
  check` match.
- Git keeps no empty dir, so `.agent/tasks/open/` vanishes when its last task
  closes; `task list` copes by catching a narrow missing-path error. Consider
  a task that keeps the dir in git (e.g. a `.gitkeep` seeded by `create` and
  kept by `close`), after which that catch could go.

## 2 · dev · progress
Done: read TASK.md, the code and the notes; the default branch is already merged.
Next: test-first, one slice per commit: (1) `ProjectClone.fetch_branch`,
`local_list_dir`, `local_read`; (2) `TaskSummary` and
`ProjectTasks.list_open_task_summaries`, plus the fetch count; (3) the pure
listing function and the `task list` parser and `main`; (4) README and
ARCHITECTURE.md. Then the host tier, ruff and mypy, `NAMES.md`, and the draft PR.

## 3 · dev · ready-for-review
Done: all acceptance criteria met, in commits on task/wcf-0028 (clone methods;
`list_open_task_summaries` with the fetch-count test; `task list` and its
pure `listing_lines`; README and ARCHITECTURE.md). Host tier, ruff and mypy
pass, and so does CI on the draft PR https://github.com/WillCodeFoundry/willcode-foundry/pull/43.
No merge conflicts. Names are in NAMES.md.
Next (reviewer): check the symlinked-TURN and upper-case-dir handling. Suggested
follow-ups, not part of this task: none beyond the planner's two.

## 4 · reviewer · changes-needed
Done: round 1 of REVIEW.md, reviewing 1ab21bc against TASK.md at e3b591a (no
other role changed it). pytest, ruff and mypy pass. Every acceptance
criterion is met; three findings block, all local fixes:
- R1: the per-project catch sits in `list_main`, against design rule 7, and no
  test reaches it.
- R6: `list_open_task_summaries` does four jobs, with the id check tangled into
  the loop.
- R7: `listing_lines` splits rows by project, then regroups them.
Next (dev): fix R1, R6 and R7 test-first, and answer each by id. Follow-ups,
fix or defer: R2 (module docstring), R3 (test the exit code and streams,
after R1), R4 (multi-line TURN), R5 (run's fix hint in a listing), R8
(`_local_ref` not used by `read`/`push_atomic`).

## 5 · dev · progress
Done: round 1's findings, in 4195ec5, 87a4ac7, 8e7f8d6 and 294b4af. No merge
was needed (the default branch has no new commits). Host tier, ruff and mypy pass.
- Answers R1: fixed in 4195ec5. The per-project catch is `read_project_listing`
  (renamed in 294b4af), tested over a good and an unreachable project; `list_main`
  only builds, loops and prints.
- Answers R2: fixed in 4195ec5.
- Answers R3: fixed in 4195ec5. A test runs `cli.main(["task", "list"])` in a
  temporary foundry instance (as `test_skills.py` does): the good project on
  stdout, the failed one as `error:` on stderr, exit 1; exit 0 when only the
  good one is named.
- Answers R4: deferred, because ADR 0011 makes `TURN` one line, so only a
  hand-edited `TURN` does this, and the shared `_turn_of` serves `read_task_turn`,
  which TASK.md says not to change. A first-line-only rule would be its own decision.
- Answers R5: fixed in 4195ec5. `_turn_of` keeps the shared first part and takes
  each caller's fix: `read_task_turn` keeps "Name the role to run instead.",
  listing says "Write the next role's name in it."
- Answers R6: fixed in 4195ec5. The id check is `_open_task_in_dir`, the turn read
  `_read_local_task_summary`; the method is now fetch, list, map.
- Answers R7: fixed in 87a4ac7. Widths first, then each project in one pass.
- Answers R8: fixed in 8e7f8d6. `read` and `push_atomic` use `_local_ref`.
Next: wait for CI on PR #43, then end the turn ready-for-review. Follow-up: R4.

## 6 · dev · ready-for-review
Done: every round 1 finding answered (entry 5): R1, R2, R3, R5, R6, R7, R8 fixed
in 4195ec5, 87a4ac7, 8e7f8d6, 294b4af; R4 deferred. All acceptance criteria
still met. Host tier, ruff and mypy pass, and CI passes on 294b4af in the draft
PR https://github.com/WillCodeFoundry/willcode-foundry/pull/43. No merge conflicts.
New names are in NAMES.md (`read_project_listing`, `_read_local_task_summary`,
`_open_task_in_dir`).
Next (reviewer): round 2. Follow-ups, not part of this task: R4 (multi-line
`TURN`), and the planner's two.

## 7 · reviewer · approved
Done: round 2 of REVIEW.md, reviewing 294b4af against TASK.md at e3b591a (unchanged; no other role changed it). pytest (host tier), ruff and mypy pass.
- R1, R2, R3, R5, R6, R7 and R8 are closed. R4 is deferred.
- The fixes raise no new findings.
Next (dev): end with `pr-ready`: mark PR #43 ready for the human. Follow-ups, not part of this task: R4 (multi-line `TURN`), and the planner's two in entry 1.

## 8 · reviewer · changes-needed
Done: added round 3 to REVIEW.md, reviewing 294b4af again. This replaces entry 7's `approved`. After round 2, the human asked for `_open_task_in_dir` to be fixed before the PR. Round 3 has one Blocking finding:
- R9: `_open_task_in_dir` builds the task with `Task.as_open`, which lowercases the dir name. It then compares the id with the dir name again to catch the case it just lowercased. The plain `Task(dir_name, Status.OPEN)` constructor already refuses upper case.
- Also under R9: `Task`'s invalid-id message should say lowercase letters.
Next (dev): fix R9 test-first and answer it by id, then end `ready-for-review`. Note that this is round 3. If the next round finds a Blocking finding still open, the reviewer ends `no-agreement` and the task goes to the human.

## 9 · dev · progress
Done: merged the default branch (#44, role models) into the task branch in
3b6ff1e, cleanly, no conflicts; host tier, ruff and mypy pass.
- Answers R9: fixed in da1c3b8. `_open_task_in_dir` builds `Task(dir_name,
  Status.OPEN)` and only wraps `Task`'s error with the path and the fix; the
  extra comparison and its own reason are gone. `Task`'s message says
  "use lowercase letters", pinned by a new test, and the `WCF-1` listing test
  now pins the whole message.
Next: wait for CI on PR #43, then end ready-for-review.

## 10 · dev · ready-for-review
Done: R9 answered (entry 9), fixed in da1c3b8; the default branch merged
cleanly in 3b6ff1e. All acceptance criteria still met. Host tier, ruff and mypy
pass, and CI passes on da1c3b8 in the draft PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/43. No new names.
Next (reviewer): round 4. Follow-ups, not part of this task: R4 (multi-line
`TURN`), and the planner's two in entry 1.

## 11 · dev · progress
Done: at the human's request, removed the single-caller helper `_open_task_in_dir`,
in 17606fe. `list_open_task_summaries` builds `Task(name, Status.OPEN)` for each dir
in one comprehension under one `try`, before any TURN is read, so the `except`
can't catch a turn error. The message changed shape, since the comprehension's
name isn't in scope in the `except`: "`.agent/tasks/open/ on agent-notes has a
dir that isn't a task id: task id 'Bad Dir' is not valid: .... Rename or remove
the dir.`" Task's error quotes the dir name; both tests pin the new wording.
Host tier, ruff and mypy pass. Recorded in NAMES.md.
Next: wait for CI on PR #43; TURN stays reviewer, for round 4 to review 17606fe too.

## 12 · dev · ready-for-review
Done: R9 fixed in da1c3b8 (entry 9); `_open_task_in_dir` removed in 17606fe at
the human's request (entry 11). All acceptance criteria still met. Host tier,
ruff and mypy pass, and CI passes on 17606fe in the draft PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/43.
Next (reviewer): round 4, covering da1c3b8 and 17606fe. Follow-ups, not part of
this task: R4 (multi-line `TURN`), and the planner's two in entry 1.

## 13 · dev · progress
Done: at the human's request, undid entry 11: 94ace56 reverts 17606fe, so the code is
as at da1c3b8 and the error message is the one R9 pinned again. Then 7008206 renames
`_open_task_in_dir` to `_open_task_for_dir`, the human's choice; recorded in
NAMES.md. Host tier, ruff and mypy pass.
Next: wait for CI on PR #43, then end ready-for-review.

## 14 · dev · ready-for-review
Done: R9 fixed in da1c3b8 (entry 9). 17606fe (entry 11) reverted in 94ace56, and
the helper renamed `_open_task_for_dir` in 7008206, both at the human's request
(entry 13). All acceptance criteria still met. Host tier, ruff and mypy pass,
and CI passes on 7008206 in the draft PR
https://github.com/WillCodeFoundry/willcode-foundry/pull/43.
Next (reviewer): round 4, covering da1c3b8 to 7008206. Follow-ups, not part of
this task: R4 (multi-line `TURN`), and the planner's two in entry 1.

## 15 · reviewer · approved
Done: round 4 added to REVIEW.md. It reviews 7008206 (fix diff 294b4af..7008206) against TASK.md at e3b591a, which is unchanged and allowed. pytest (host tier), ruff and mypy pass.
- R9 is closed: `_open_task_for_dir` builds `Task(dir_name, Status.OPEN)`, and `Task`'s message says lowercase letters, pinned by tests. R1–R3 and R5–R8 stay closed; R4 stays deferred.
- New: R10 (Follow-up). The comment on `_TASK_ID` (`task.py:31-33`) still says "Matched after lowercasing". It isn't blocking.
Next (dev): end with `pr-ready`, and mark PR #43 ready for the human. Fixing R10 in this task is optional: answer it by id, fixed or deferred. Follow-ups, not part of this task: R4 (multi-line `TURN`), R10, and the planner's two in entry 1.

## 16 · reviewer · progress
Done: at the human's request, recorded a suggested follow-up task: making task ids and case consistent. This entry doesn't change entry 15's outcome, and TURN stays dev.
- The two ways to build a `Task` treat case differently, and no name or type says which a caller gets:
  - `Task.as_open` and `Task.from_id_and_status` (`src/foundry/task.py`) lowercase the id first.
  - The constructor checks the id as given, which `_open_task_for_dir` relies on to refuse an upper-case dir.
- An id refused after lowercasing is quoted lowercased, not as typed. For example, `create WCF..1` reports `'wcf..1'`.
- The comment on `_TASK_ID` (`task.py:31-33`) says ids are "Matched after lowercasing". That is R10.
- GLOSSARY.md's **Task id** says only "lowercase". It doesn't say whether a typed id is lowercased or refused.
- One direction, for the planner and the human to settle: name the lowercasing step for what it does, or keep one way to build a `Task` that checks the id.
Next (dev): unchanged from entry 15, `pr-ready`. Fixing R10 now, a comment-only change, is optional. If you defer it, answer `R10: deferred` to this follow-up.
Next (human): if worth doing, create the follow-up task with `foundry task create`, for the planner to plan.

## 17 · dev · pr-ready
Done: default branch already merged (nothing new on origin/HEAD). Host tier, ruff
and mypy pass on 7008206, and CI passes on it. Round 4 is `Verdict: approved`;
all 12 acceptance criteria met, as the reviewer checked. No commits after the
approval. PR title and body written from the `pr` skill, and PR #43 marked ready:
https://github.com/WillCodeFoundry/willcode-foundry/pull/43
- Answers R10: deferred, because fixing it would be a commit after the approval,
  sending the task back to review for a comment; it belongs with the task-id case
  follow-up the reviewer recorded in entry 16, which owns that comment.
Next (human): review and merge PR #43. Follow-ups, not part of this task: R4
(multi-line `TURN`), R10 with entry 16's task-id case consistency, and the
planner's two in entry 1.

## 18 · reviewer · changes-needed
Done: at the human's request, round 5 added to REVIEW.md. It reviews 7008206 again, for names and the smell behind `_turn_of`.
- The human's decision: TASK.md's out-of-scope line on changing `ProjectClone.read`, `read_task_turn` and `in_scratch_clone` no longer holds. Any change that makes the code simpler and easier to read is in scope. (the human)
- The human chose the names: `_tracking_ref`, `fetched_list_dir`, `fetched_read`, `chosen_projects`, `NotOnBranchError`.
- This goes past the three-round limit only because the human asked. Nothing is in dispute.
- Open, all Blocking: R10 (fix it now), R11–R14 (renames), R15 (move `read_task_turn` onto `fetched_read`, delete `ProjectClone.read`, and fold `_turn_of` and `_read_local_task_summary` into one method).
Next (dev): fix R10–R15 and answer each by id. Update NAMES.md (remove `_turn_of`'s mentions, add the renames and the new method). Then end `ready-for-review` for round 6. PR #43 should go back to draft until then.
Follow-ups, not part of this task: R4; `_require_command` returns a value, unlike the other `_require_*` (round 5); the task-id case follow-up in entry 16; the planner's two in entry 1.

## 19 · dev · ready-for-review
Done: round 5's findings, after merging origin/HEAD (nothing new). PR #43 is back
to draft. Host tier, ruff and mypy pass, and CI passes on 3e9e4fa:
https://github.com/WillCodeFoundry/willcode-foundry/pull/43
- Answers R10: fixed in 9e222b1. The `_TASK_ID` comment says the constructor
  matches the id as given, and `from_id_and_status` (with `as_open` and
  `as_closed` through it) lowercases a typed id first.
- Answers R11: fixed in 009ea31. `_local_ref` is `_tracking_ref`, and returns only
  the ref; its two `<ref>:<path>` callers build the object spec themselves.
- Answers R12: fixed in 009ea31. `fetched_list_dir`, `fetched_read`, their tests
  and the section comment.
- Answers R13: fixed in 009ea31. `chosen_projects`, and its test.
- Answers R14: fixed in 009ea31. `NotOnBranchError`, its docstring now naming the
  wrong-kind case.
- Answers R15: fixed in 3e9e4fa. `read_task_turn` reads through `fetched_read`
  after `get_task_by_id`'s fetch; `ProjectClone.read`, `_turn_of` and
  `_read_local_task_summary` are gone, replaced by
  `_read_fetched_turn(task, *, fix)`. New test `test_a_dir_at_turn_is_no_turn`
  (it failed before: `read` returned the tree listing). The message wording is
  unchanged. One behaviour change in listing: all dir names are checked as ids
  before any `TURN` is read, so an invalid-id dir is reported ahead of an earlier
  task's missing `TURN`; either way the project fails.
- NAMES.md updated: renames recorded, `_turn_of`/`_read_local_task_summary`
  replaced by `_read_fetched_turn`, `_tracking_ref` added.
All acceptance criteria still met.
Next (reviewer): round 6, covering 7008206..3e9e4fa. Follow-ups, not part of this
task: R4 (multi-line `TURN`); `_require_command` (round 5); the task-id case
follow-up in entry 16; the planner's two in entry 1.

## 20 · dev · ready-for-review
Done: at the human's request, merged origin/main after #45 (wcf-0029: task ids
must match `[a-z]+-[0-9]{4,}`, never lowercased) in 46b7d16. Conflicts:
- `src/foundry/task.py`: took main's side in both hunks. Its pattern comment and
  message replace R10's comment (9e222b1) and R9's message, which described the
  lowercasing main removed. So R10's fix is superseded, not lost: the comment now
  matches the code.
- `tests/test_task.py`: kept both sections (this task's listing tests, main's
  uppercase-id test). Moved this task's tests to valid ids, as main moved its own
  (`t0` → `tst-0000`, `c0` → `cls-0000`, `t1` → `tst-0001`, `a2`/`b1` →
  `aaa-0002`/`bbb-0001`). The alignment test uses `t-0001` against `wcf-0007`,
  so the id column still pads. Dropped
  `test_an_invalid_task_id_is_told_letters_must_be_lowercase` (R9's): it pinned
  the old message, and main's `test_task_ids_not_matching_the_pattern_are_refused_as_given`
  pins the new one exactly.
- `_open_task_for_dir` stays: `Task.as_open` no longer lowercases, but the wrapper
  is what names the dir and says "Rename or remove it.", as TASK.md asks.
  `test_an_upper_case_dir_is_not_a_task_id_either` still passes unchanged.
Host tier, ruff and mypy pass; CI passes on 46b7d16. All acceptance criteria
still met. No new names.
Next (reviewer): round 6, covering 7008206..46b7d16, the merge included. The
task-id case follow-up from entry 16 is now done by wcf-0029. Follow-ups left:
R4 (multi-line `TURN`); `_require_command` (round 5); the planner's two in entry 1.

## 21 · dev · ready-for-review
Done: at the human's request, rewrote PR #43's body, which still described round 4:
the round 5 names (`chosen_projects`, `fetched_list_dir`, `fetched_read`,
`NotOnBranchError`, `_read_fetched_turn`); `ProjectClone.read` removed and
`read_task_turn`'s change (R15) under Merge Danger, with the scope change noted as
the human's (round 5); the old `Task` message line dropped, since the merge took
main's; follow-ups now R4 and `_require_command`; evidence on 46b7d16 with
`test_a_dir_at_turn_is_no_turn`. The PR stays a draft. No code change.
Next (reviewer): round 6, as entry 20 says. The dev rewrites the body again from
the `pr` skill after approval.

## 22 · dev · ready-for-review
Done: at the human's request (no functions returning None for callers to branch
on), 1306eb8 replaces `ProjectClone._object_type`, which returned None for any
`git cat-file` failure, with `_require_on_branch(branch, path, entry_type)`: it
uses `git ls-tree`, so a missing path raises `NotOnBranchError` and any other git
failure a `GitError`, no longer read as "no open tasks". It matches the entry's
name exactly, since `ls-tree` lists a dir's contents for "dir/". Tests added for
"dir/" and a prefix of a dir's name. NAMES.md updated. Host tier, ruff and mypy
pass; CI passes on 1306eb8.
- Asks D1 → human: the same pattern remains as data, not returns:
  `ProjectListing.error: str | None`, which `listing_lines` splits on with
  `is None`, and `--turn`'s `str | None`, which `_with_turn` branches on. Change
  them too? TASK.md asks for "each project's summaries or error" passed to the
  printing function, and round 1 judged the pair below the bar.
Next (reviewer): round 6, covering 7008206..1306eb8, the merge included.

## 23 · dev · ready-for-review
Done: at the human's request, a8b933b inlines `_with_turn` (one caller, one
comprehension) into `listing_lines`, rather than renaming it or using `filter`,
which would need a lambda and a `list()`. No behaviour change; the `--turn` tests
are unchanged and pass. Host tier, ruff and mypy pass; CI passes on a8b933b.
D1 (entry 22) is still open; its `--turn` half stands as is: the `turn is None`
check now sits in the comprehension.
Next (reviewer): round 6, covering 7008206..a8b933b, the merge included.

## 24 · dev · ready-for-review
Done: at the human's request, 3429522 separates filtering from printing.
`listing_lines(listings)` only formats. `ProjectListing.with_turn(turn)` keeps the
tasks whose turn is `turn`, and sets the new field `no_tasks_note` to "no open
tasks with turn ROLE" when the project had tasks but none match.
`listings_with_turn(listings, turn)` is the one place no `--turn` (None) is
handled, so `list_main` still decides nothing (design rule 7). Output unchanged.
Tests: `with_turn` and `listings_with_turn` tested directly; `listing_lines`
calls lose `turn`. This departs from TASK.md's Context, which had the printing
function take the `--turn` filter; the human asked for it. NAMES.md and the PR
body updated. Host tier, ruff and mypy pass; CI passes on 3429522.
D1 (entry 22): its `--turn` half is now confined to `listings_with_turn`; the
`ProjectListing.error` half is still open.
Next (reviewer): round 6, covering 7008206..3429522, the merge included.

## 25 · dev · ready-for-review
Done: at the human's request, 0644fdc replaces the method `ProjectListing.with_turn`
with the function `listing_with_turn(listing, turn)`, which builds a new
`ProjectListing` explicitly (the method returned a new tuple too, through
`_replace`, but read as changing its own). `listings_with_turn` calls it per
project. The test also checks the listing given keeps its 4 tasks. Output
unchanged. NAMES.md and the PR body updated. Host tier, ruff and mypy pass; CI
passes on 0644fdc.
D1 (entry 22): the `ProjectListing.error` half is still open.
Next (reviewer): round 6, covering 7008206..0644fdc, the merge included.

## 26 · dev · ready-for-review
Done: at the human's request, 4a99b2f renames `listing_with_turn` to
`filter_project_listing` and inlines `listings_with_turn`. `filter_project_listing`
now takes `turn: str | None` and returns the listing as it is for None, so
`list_main` applies it in the comprehension that reads each listing, with no
branch (design rule 7). Tests: `filter_project_listing(store, None) is store`;
the others call it directly. Output unchanged. NAMES.md and the PR body updated.
Host tier, ruff and mypy pass; CI passes on 4a99b2f.
D1 (entry 22): the `ProjectListing.error` half is still open.
Next (reviewer): round 6, covering 7008206..4a99b2f, the merge included.
