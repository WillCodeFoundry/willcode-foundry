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
