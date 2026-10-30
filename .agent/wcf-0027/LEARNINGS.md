# Learnings
- 2026-10-30 [decision] — Kept Task and ProjectTasks tests in one `tests/test_task.py`: they share the bare-repo and signer fixtures, and a second file would import from the first or duplicate them.
- 2026-10-30 [decision] — `Task.__post_init__` requires an already-lowercase id; `from_id` lowercases. So the "not valid" message for `X.LOCK` quotes `x.lock`.
- 2026-10-30 [proposal] — Reviewer could not run the checks in round 1: `uv run pytest` fails with "Failed to spawn: pytest" because `pyproject.toml` sets `default-groups = []`, so the dev group is absent until `uv sync --group dev`. Only CONTRIBUTING.md says so. Proposed changes:
  1. Project `AGENTS.md`, "Checks": add "Run `uv sync --group dev` first, or `uv run pytest` fails to spawn pytest" beside the pointer to CONTRIBUTING.md.
  2. `code-review` skill, Behaviour brief: say "pass the setup commands (CONTRIBUTING's install step) as well as the test commands, and run them in the throwaway clone, never in the code checkout".
  3. `reviewer/ROLE.md`: say the reviewer runs the project's checks once, in a throwaway clone, and puts the result in the round.
- 2026-10-30 [process] — I passed the sub-agents only `uv run pytest` and never read CONTRIBUTING.md's setup step, so none of us ran the checks in round 1. Fixed in round 2.
- 2026-10-30 [tooling] — `gh pr edit` fails here with missing `read:org` scope (GraphQL); use `gh api -X PATCH repos/<repo>/pulls/<n> -f title=... -F body=@file`. `gh pr ready` works.
- 2026-10-30 [tooling] — Reviewer: `gh` gets HTTP 401 (bad GH_TOKEN) in the reviewer sandbox, but the repo is public, so `env -u GH_TOKEN curl -s https://api.github.com/repos/WillCodeFoundry/willcode-foundry/pulls/<n>` reads the PR title and body.
- 2026-10-30 [process] — Owner asked to rewrite REVIEW.md from scratch (updated code-review skill), restarting at round 1; earlier rounds and R1–R6 are in git history (e.g. 1334389). This overrides ROLE.md's "never edit earlier rounds" for this one rewrite.
- 2026-10-30 [proposal] — `code-review` skill: the fresh round 1 missed three smells the owner then found or asked about: the `turn` sentinel in `run.main` (R7), the duplicated `close_main`/`reopen_main` and scratch-clone setup (R6), and `main` untested (R8). Causes, and a proposed change for each:
  1. **Smells share a sub-agent, and a 400-word / 5-finding budget, with the documented standards.** Docs and ADRs used it up. → Run smells as a fourth sub-agent, **Design**, with its own budget.
  2. **The brief asks for findings, not coverage, so a skipped smell can't be seen.** → The Design sub-agent returns a table: every function or method the diff adds or changes, against every smell, each cell "none" or a finding id. The aggregator checks the table is complete before writing the round.
  3. **It reads hunks, not functions.** R7 shows only when `main` is read whole and compared with its version at the fixed point (one `if` became a sentinel, a re-test and an assert). → Brief: "Read each changed function whole, at HEAD and at the fixed point. Ask whether the change made it simpler or more tangled, and flag a regression even if each hunk looks fine." Also: "Compare sibling functions the diff adds side by side (`close_main`/`reopen_main`), and every new copy of an existing shape (the scratch-clone setup)."
  4. **The general rules filter smells out.** "Who would hit it" is a user-path test, and "Fewer, or none, is a good result" invites stopping early. → For the Design axis, "who hits it" is the next dev changing that code. Drop "fewer is good" from that brief.
  5. **Smells are always Follow-ups, and Follow-ups get deferred.** So a smell is never addressed in the task that adds it. → New bar: a smell **the diff introduces** is Blocking when its fix is local, meaning one or two functions with no change to an interface DESIGN.md fixes. It is a Follow-up only when the fix needs a design change, and then it goes to the owner as a design question.
  6. **The aggregator drops a smell that DESIGN.md decides, silently.** → Keep it as "design question for the owner", named in the round, not dropped. The owner decides, and the architect changes DESIGN.md if so.
  7. **A criterion shown only by reading is not raised as a finding.** The Spec brief says it is partial, but the reviewer listed it in the table and moved on. → Spec brief: "Every partial criterion is a finding."
  - Matching change to `reviewer/ROLE.md` and `dev/ROLE.md`: the dev may defer a Design Follow-up only with the owner's say in REVIEW.md, not on their own.
- 2026-10-30 [proposal] — Amends the `code-review` proposal above, agreed with the owner:
  1. **Name the fourth reviewer "Smells", not "Design".** "Design" reads as checking against DESIGN.md, which is Spec's job.
  2. **Design questions go to the owner.** A finding is a "design question" when any of these holds:
     - its fix would change a decision in DESIGN.md (an interface, a module boundary or a type);
     - DESIGN.md asks for something a project rule forbids (here: the `TypeError` guard against ARCHITECTURE.md rule 6);
     - one smell recurs from one decision;
     - no honest local fix exists.

     When a round has a design question still open, the reviewer writes `human` in `TURN`, not `dev`. The owner then sends it to the architect or accepts the code as is. Findings fixable inside the current design stay with the dev.
  3. **Matching change to `reviewer/ROLE.md`:** add this case beside the round 3 exception for writing `human`.
- 2026-10-30 [proposal] — Design questions found in review: routing them back to the architect, agreed with the owner. The flow is reviewer → human → architect → dev → reviewer. The architect's change to DESIGN.md is approved by the human, so it needs no review turn of its own. Round 2 checks it together with the code. Proposed changes:
  1. **`architect/ROLE.md`, Method:** when the turn comes from a review rather than the planner, start from REVIEW.md's "Design questions" and "Waits for the design" in the latest round, not from TASK.md alone. Answer each question by changing DESIGN.md, or by agreeing with the human that the design stands.
  2. **`architect/ROLE.md`, step 6:** "With `DESIGN.md` pushed, or once you and the human agree it stands, the turn is the `dev`'s." When the design stands, say so for each question under "In progress" in PROGRESS.md, since the architect can't write REVIEW.md.
  3. **`reviewer/ROLE.md`:** check DESIGN.md's history as TASK.md's is checked. Each change must be signed by the architect's identity. Report any other change at the top of the round.
  4. **`reviewer/ROLE.md` / `code-review`:** in the round after an architect turn, settle each design question (closed, or accepted as is). Re-judge every "Waits for the design" finding against the new DESIGN.md, and treat the DESIGN.md diff as part of the fix diff.
- 2026-10-30 [proposal] — `architect/ROLE.md` changes for turns that come from a review, agreed with the owner. This replaces item 1 of the previous entry.
  1. **Method, opening paragraph:** replace "Answer it by reading `TASK.md`, then telling the human which design questions you will review with them" with:
     > Your session starts on foundry's opening prompt, before the human has said anything. First, find where this turn comes from:
     > - **From a review:** `REVIEW.md` exists in your task's notes, and its latest round has a "Design questions" section. Follow "When the turn comes from a review".
     > - **From the planner:** otherwise. Read `TASK.md`, then tell the human which design questions you will review with them, and follow the steps below.

     Why the notes are the signal: only the reviewer writes design questions, and only its next round settles them. Rejected: putting the reason in `TURN` (ADR 0011 makes it one line naming a role), relying on the human to say it, and a reviewer note in `PROGRESS.md` (not the reviewer's file). Edge case: when the planner rescopes after a review, the architect takes the review path. That's acceptable, since the questions are still open.
  2. **A new section, "When the turn comes from a review":**
     1. Read the latest round of `REVIEW.md`: "Who reads what", then "Design questions".
     2. Read the findings it lists as "Waits for the design". Don't solve them; make the design leave the dev a clear way to fix them. Skip the independent ones.
     3. Read the `DESIGN.md` decisions each question quotes, then `TASK.md`, then the cited code on `$AGENT_TASK_BRANCH`.
     4. Work through each question with the human in rounds, as in "Asking questions": change `DESIGN.md`, or agree the design stands.
     5. Draft any change to `DESIGN.md` and get approval before writing it, as in Method. Under "Decisions", write "Answers R<n>." and name any decision it reverses.
     6. When the design stands, write "R<n>: design stands, because <why>" under "In progress" in `PROGRESS.md`.
     7. Commit and push. The turn is the `dev`'s either way. Never edit `REVIEW.md`.
  3. **Boundaries:** allow the "design stands" lines under "In progress" in `PROGRESS.md`, beside `DESIGN.md`, `TURN` and "Blockers".
- 2026-10-30 [git] — Moving files on disk then `git add --all` re-reads them through your git config: a tracked file matching `core.excludesFile` is dropped, and `core.autocrlf=input` rewrites CRLF blobs. `git mv` moves index entries as they are, and a later `add --all` keeps them. Tested on git 2.53.
- 2026-10-30 [decision] — The three `foundry task` reports go through one `report(action, ...)` keyed by the action, like `repo.py`'s `report`. Kept `close_main`/`reopen_main` separate: a shared body would need a switch on the action.
