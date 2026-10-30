# Learnings
- 2026-10-30 [decision] — Kept Task and ProjectTasks tests in one `tests/test_task.py`: they share the bare-repo and signer fixtures, and a second file would import from the first or duplicate them.
- 2026-10-30 [decision] — `Task.__post_init__` requires an already-lowercase id; `from_id` lowercases. So the "not valid" message for `X.LOCK` quotes `x.lock`.
- 2026-10-30 [proposal] — Reviewer could not run the checks in round 1: `uv run pytest` fails with "Failed to spawn: pytest" because `pyproject.toml` sets `default-groups = []`, so the dev group is absent until `uv sync --group dev`. Only CONTRIBUTING.md says so. Proposed changes:
  1. Project `AGENTS.md`, "Checks": add "Run `uv sync --group dev` first, or `uv run pytest` fails to spawn pytest" beside the pointer to CONTRIBUTING.md.
  2. `code-review` skill, Behaviour brief: say "pass the setup commands (CONTRIBUTING's install step) as well as the test commands, and run them in the throwaway clone, never in the code checkout".
  3. `reviewer/ROLE.md`: say the reviewer runs the project's checks once, in a throwaway clone, and puts the result in the round.
- 2026-10-30 [process] — I passed the sub-agents only `uv run pytest` and never read CONTRIBUTING.md's setup step, so none of us ran the checks in round 1. Fixed in round 2.
- 2026-10-30 [tooling] — `gh pr edit` fails here with missing `read:org` scope (GraphQL); use `gh api -X PATCH repos/<repo>/pulls/<n> -f title=... -F body=@file`. `gh pr ready` works.
