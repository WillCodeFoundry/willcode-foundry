# Implementer brief template

A brief records decisions already made with the user, so another agent can implement them consistently. Write decisions as decided, give each a reason, and fill in every section. Delete a section only if it truly has nothing in it.

```markdown
# Brief: <one-line summary of the change> on `<branch>`

You are working on **<repository>**, branch `<branch>` (commit `<sha>` when this brief was written). Base your work on that branch.

This is a **<mechanical | simplification>** change: <one sentence on what kind of change, and what stays the same>. Every name and decision below was agreed with the repository owner; don't substitute your own. Where something isn't covered, follow the conventions below and list what you chose in your summary.

## Behaviour changes, the only <n>

<A numbered list. Write "None" if there are none. Anything not listed here must not change.>

## Safety net

- <Is the code to be changed covered by tests? If not: the first commit adds characterisation tests for <areas>, before any rename or move.>
- <Public API: "application, renames are internal", or "library: keep deprecated aliases for <names> until <version>".>
- <Every patch or mock target whose import path this brief changes, updated in the same commit as the move. Or "none".>
- <Tests that must keep using patching until a later injection step, marked as temporary. Or "none".>

## Glossary

| Term | Means | Lives in |
|---|---|---|
| ... | ... | ... |

<Note any word that is deliberately *not* used, and why.>

## Conventions

**1. <rule>.** <why>. <exceptions, each with its reason>
**2. ...**

## Renames

### <module, package or area>

| Now | New | Notes |
|---|---|---|
| ... | ... | ... |

## Moves

### New module `<path>`

<What it owns, what it exports, what it must not depend on, and what error it raises on bad input.>

### What leaves `<module>` / what stays

### Consequences

<Invariants that disappear, and parameters that become derivable.>

## Inline

| Helper | Becomes |
|---|---|

## Defensive code replaced by loud failures

| Where | Now | New |
|---|---|---|

**Keep tolerant:** <inputs that are themselves what is being checked>.

## <Output format, if it changes>

<An exact example of the new output.>

## Tests

<Renames, new tests (including a boundary or self-check test where one makes a claim a checked fact), and tests that move to the caller.>

## Docs

<Which sections and comments to update, and the vocabulary to use.>

## Out of scope: don't do these now

- <Each deferred item, so the implementer doesn't start it.>

## Done when

- <The project's own checks, by command: tests, lint, format, types, build.>
- A search (e.g. `git grep -nE`) finds none of these in <paths>, ignoring the history:
  - <one pattern per old name>
- The summary lists any name the implementer chose themselves, and any user-visible message, path or output that changed.
- Commits are split into: <parts>. **Every commit leaves tests, lint and types passing.** Each commit message says why, not only what.
```

## Tips

- **Name things exactly.** Give the old and new names, file paths, signatures where they change, and the literal strings of new error messages.
- **When an argument order changes, say so explicitly.** It's an easy detail to miss in a rename table.
- **State exceptions to conventions in the conventions section,** not scattered through the tables.
- **Keep the brief current.** When the implementer pushes back and you agree, edit the brief and add the old name to the search list if it shouldn't survive.
