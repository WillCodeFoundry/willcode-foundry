# A task's turn is one line its roles write

A task's `TURN` file on `agent-notes` names the role whose turn it is, or `human`. Each role writes the next one when its turn ends, as its `ROLE.md` says, and pushes it like any other note. `foundry run` without a role reads it, so the role is launched without being named. Nothing checks a hand-off. The only real gate is the pull request your code-owner approval guards ([ADR 0001](0001-github-enforces-hooks-only-guard.md)), and the dev's token can open one whatever any file says.

## Considered options

- **A lifecycle state machine in code, with events, a task command and a pre-push check of each transition (#22).** About 2,000 lines to guard a mistake you see at the next launch. Its goals and events repeated `ROLE.md` and `REVIEW.md`'s verdict, and its hand-off note repeated `PROGRESS.md`.
- **Deriving the turn from the notes, such as `REVIEW.md`'s last verdict.** No new file, but every rule would live in foundry, out of sight of the roles that follow it.
- **Making ROLE required, as before.** You had to know whose turn it was. Naming it still overrides the file.

Source: #22.
