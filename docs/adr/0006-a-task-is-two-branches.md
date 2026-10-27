# A task is a branch plus its notes on a separate `agent-notes` branch

A task is its code branch, `task/<id>`, and its notes dir, `.agent/<id>/` on `agent-notes`. The notes branch is an orphan, sharing no history with the code, so notes never reach a code review and every role can record its work. `foundry task create` makes both with the owner's own git access and signing key, in one `git push --atomic`, so either both exist or neither does. A task's names are built in one place, `foundry.task.Task`, and reach the sandbox as session variables, so the kit spells none of them out.

## Considered options

- **Writing the files through the GitHub API.** Two writes, with no way to make them one.
- **Deriving the names again in the kit's shell.** Two spellings, held together only by a test.

Source: #4, #7.
