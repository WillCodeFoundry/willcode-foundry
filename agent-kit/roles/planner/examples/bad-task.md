# Task 17: Improve API performance

<!-- Annotated: each note says why the line fails the checklist. -->

## Goal
Make the API faster.
<!-- No why, no measure. "Faster" cannot be checked by a reviewer. -->

## Acceptance criteria
- [ ] The API is faster.
<!-- No id, and it restates the goal. QA cannot test it without a judgement call. -->
- [ ] AC2: Add a `ResponseCache` class in `api/cache.py`, copying `_lookup` from `api/sessions.py`.
<!-- Says how, not what: which class, which file, which code to copy. That is the dev's PLAN.md, approved before code. -->
- [ ] AC3: <Testable statement.>
<!-- Placeholder left in from the template. -->

## Out of scope
- OS1: Changing `_serialize_row`.
<!-- Names a private function, not a behaviour. A dev who finds the slowness there must now work around it. -->

## Risks
<!-- Empty, though `api/handlers.py` has an open follow-up about this very slowness. The planner never searched for it. -->

## Open questions
- Which endpoints matter most?
<!-- Non-empty: the task is not ready. Should have been answered before release. -->
