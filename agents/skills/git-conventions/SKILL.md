# Commit messages and pull requests

How to write commit messages and pull requests. The project's own `AGENTS.md`
or `CONTRIBUTING.md` wins where it says otherwise.

## Commit messages

```
<type>(<scope>): <summary>

<body>

<footer>
```

### Summary line

- Under 72 characters, 50 if you can.
- Imperative mood: "add", not "added" or "adds". It should complete the
  sentence "if applied, this commit will ...".
- No trailing full stop.
- `<type>` says what kind of change it is:
  - `feat`: new behaviour users or callers can see
  - `fix`: corrects wrong behaviour
  - `refactor`: restructures code without changing behaviour
  - `perf`: improves performance without changing behaviour
  - `test`: adds or fixes tests only
  - `docs`: documentation only
  - `build`: build system or dependencies
  - `ci`: CI configuration
  - `chore`: anything else that touches no production code
- `<scope>` is the area touched, optional: a module, package or component
  name as it appears in the code, such as `api`, `auth`, `cli`.
- One logical change per commit. If the summary needs "and", split it.

### Body

- Separated from the summary by a blank line. Wrap at 72 characters.
- Say **why** the change is needed and **why this way**. The diff already
  shows what changed.
- Mention alternatives you rejected and anything surprising, so the next
  reader does not retry them.
- Omit the body for trivial changes where the summary says everything.

### Footer

- `Task: <task-id>`, always.
- `BREAKING CHANGE: <what breaks and how to migrate>` when it does.
- No `Co-authored-by` or other attribution lines.

### Examples

```
fix(api): return 429 instead of 500 when rate limit store is unavailable

The limiter raised on a cache miss, which surfaced as a 500 to clients and
hid the real problem. Fail open instead: let the request through and log a
warning, since a brief window without limiting is cheaper than an outage.

Rejected failing closed (503): it turns every cache blip into downtime.

Task: WCF-0042
```

```
test(api): cover Retry-After header on 429 responses

Task: WCF-0042
```

### Avoid

- `fix bug`, `wip`, `update`, `changes`: say which bug, which update.
- Summaries that describe the diff: "change X to Y" without why.
- Mixing a refactor with a behaviour change in one commit.

## Pull requests

### Title

Same rules as a commit summary: imperative, under 72 characters, typed and
scoped. If the PR has one commit, reuse its summary. Prefix the task id:

```
[WCF-0042] feat(api): rate-limit unauthenticated requests
```

### Description

```markdown
## What
One or two sentences: the change, from the reviewer's point of view.

## Why
The problem this solves and where it came from. Link the task.

## How
The approach, and any decision a reviewer might question: alternatives
rejected, trade-offs accepted, anything non-obvious in the diff.

## Testing
How you verified it. Which tests were added, what you ran by hand, what you
could not test and why.

## Notes for the reviewer
Where to start reading. Anything out of the ordinary: a file that looks
changed but is only moved, a deliberate deviation from a project convention.
```

- Keep "What" short; it is what shows up in the merge commit and release notes.
- "How" is where to put the reasoning from your commit bodies, consolidated.
- Leave out a section if it would only say "n/a".
- A PR is one task. If it does more, the task was two tasks.

### Checklist before opening

- [ ] Title is imperative, typed, under 72 characters, prefixed with the task id in brackets
- [ ] Every commit on the branch has a proper message; squash fixups
- [ ] Diff against `main` contains only what the task needs
- [ ] Description states how it was tested
- [ ] Every acceptance criterion in `TASK.md` is addressed or explicitly deferred
