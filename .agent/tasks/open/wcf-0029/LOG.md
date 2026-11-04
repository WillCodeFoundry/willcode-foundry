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
