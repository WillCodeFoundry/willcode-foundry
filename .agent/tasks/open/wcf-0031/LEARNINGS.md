# Learnings
- 2026-11-04 [decision] — `LOG.md` is read from the checkout with a new `ProjectClone.read`, not `fetched_read`:
  `Git.output` runs git in text mode with `errors="replace"`, folding CRLF and replacing bytes that aren't UTF-8,
  which breaks "unchanged byte for byte". `read` and `write` use UTF-8 with `surrogateescape` and `newline=""`.
  Not handled: a global `core.autocrlf=input` still folds CRLF when `commit` runs `git add --all`, as for `close`.
- 2026-11-04 [decision] — `ProjectClone.write` now unlinks a link before writing. Without it, a `TURN` that is a
  link (which `task list` already reads as its target's name) made foundry write to the target, outside the clone.
  A linked or dir `LOG.md` is refused as "has no LOG.md", since `read` takes only regular files.
- 2026-11-04 [decision] — An empty `LOG.md` gets no newline before the entry's blank line: TASK.md's "a newline
  added first if the file didn't end with one" reads as applying to a file with text, so the result starts "\n## 1".
- 2026-11-04 [decision] — Replaces the two `ProjectClone` entries above, at the human's call: no `read`, and
  `write` raises on a link rather than replacing it. `LOG.md` is read with `fetched_read`, so "byte for byte" holds
  for UTF-8 logs with LF line endings, which agents write. CRLF folds to LF and bytes that aren't UTF-8 become
  U+FFFD (`Git.output`'s text mode). A linked `TURN` or `LOG.md` is refused, naming the path, with nothing pushed.
- 2026-11-04 [review] — Anything foundry appends to a task's notes from outside its session, such as `foundry task turn` writing LOG.md, breaks agent-kit/AGENTS.md's claim that `pull --rebase` on agent-notes never conflicts. Before then, each file in a task's notes dir had only one writer at a time. Raised as R3.
- 2026-11-04 [review] — The Names sub-agent, given only the skill, passed three names that the precedents in earlier tasks' REVIEW.md and NAMES.md would have flagged: a near-twin with a different contract, a `require_` that doesn't name its result, and a glossary word (Turn vs Role). [proposal] code-review skill: give the Names brief the earlier tasks' naming findings and renames as precedent.
- 2026-11-04 [decision] — R3: handing on a running task is left to the human to avoid, with a README sentence,
  rather than recovery steps in agent-kit/AGENTS.md. Accepted risk: an agent that does hit the LOG.md rebase
  conflict has no instruction for it. Rejected: a running-sandbox check (new machinery), `merge=union` (hides
  duplicate entry numbers).
- 2026-11-04 [decision] — R4 (a multi-line TURN) deferred, not fixed: TASK.md fixes `<old>` as TURN's stripped
  text, so treating it as `none` or refusing it both change an acceptance criterion. That is the planner's call.
- 2026-11-05 [decision] — The human relaxed "byte for byte": `log_with_turn_entry` keeps the log's text but for
  the whitespace at its end. Checked against `pre-commit`'s `_require_log_only_added_to`: it compares an agent's
  staged LOG.md with origin's, which after a handoff is foundry's normalised text, so agents still pass.
- 2026-11-05 [testing] — `tests/test_project_tasks.py` imports `ProjectRepository` from `tests.conftest` under
  `TYPE_CHECKING` only, for its helpers' annotations: mypy rejects returning Any from an untyped fixture.
  Rejected: dropping the helpers (19 call sites), or a shared test module (the human wants none).
- 2026-11-05 [decision] — Proposed `OPEN_TASK`-style constants for the seeded tasks' paths, then didn't replace
  the literals: `project_repository.open_task.log_file` is no shorter than `".agent/tasks/open/tst-0000/LOG.md"`,
  and reads less directly. `ProjectRepository.open_task` and `closed_task` seed the fixture only.
- 2026-11-05 [testing] — Replaces the TYPE_CHECKING entry above. CONTRIBUTING.md:42 already says shared test
  helpers live in `tests/support/` and the conftests hold only fixtures and hooks; I missed it when splitting.
  The human chose to follow it: `ProjectRepository` and the git helpers are in `tests/support/project_repository.py`.
  The task helpers take `ProjectTasks`, so no test imports from conftest. Read CONTRIBUTING's test section before
  moving test code.
- 2026-11-05 [decision] — The human dropped the old turn from a handoff's entry, commit and stdout. Its stand-in for
  no turn, "none", could be a role's name, since config/foundry.yaml accepts any; a sentinel string in a field of
  role names is a collision waiting. Rejected: `str | None` with "from X to Y" prose (a function that sometimes
  returns None), and "no turn" as the stand-in (still a sentinel).
- 2026-11-05 [review] — When the human approves a TASK.md change in a dev session, the dev's commit isn't an allowed signer, so the reviewer must report it however clearly LOG.md attributes it to the human. Routing it through the planner's `task-question` costs one turn and keeps TASK.md's history checkable. [proposal] AGENTS.md: say that a TASK.md change the human decides in another role's session is recorded by the planner, or by a commit the human signs, never by that role.
- 2026-11-05 [testing] — To show a check runs before any git, a missing repository isn't enough:
  `ProjectTasks.in_scratch_clone` runs `git init` and `remote add` locally, and only `get_task_by_id` reaches the
  remote. A stand-in `git` first on PATH that leaves a mark catches it. Check such a test by moving the code it
  guards and watching it fail.
- 2026-11-05 [decision] — Reworded DESIGN.md for "handoff" (P1) without a new grilling round: GLOSSARY's
  Avoid list ruled out the old words, and no decision changed.
