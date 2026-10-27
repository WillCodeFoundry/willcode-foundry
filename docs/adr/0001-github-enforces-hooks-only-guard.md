# GitHub enforces what must hold; hooks in the sandbox only guard against mistakes

The agent can run anything inside its sandbox, so a hook there can be skipped: with a script, an alias, or an edit to `.git/config`. So every rule that must hold whatever the agent does is enforced on the server, by the project's GitHub rulesets, which agents can't bypass. The git hooks and the Claude Code hooks keep only rules GitHub can't express, such as "push only this task's branch", and say why when they refuse.

A hook that enforces a rule blocks when it can't check it: `session-check` treats a failing git as unsaved work. A guardrail prefers a rare miss to a false refusal: `guard-bash` scans a command it can't parse rather than refusing it, since a false refusal teaches the agent to work around it.

## Considered options

- **Hooks as the boundary.** `guard-bash` once parsed shell and git options in about 250 lines and still couldn't close every path. It was cut to about 25.
- **Refusing a commit without its `Task:` trailer.** Replaced by adding the trailer, since GitHub's commit-message rules need Enterprise.

Source: #18, #20.
