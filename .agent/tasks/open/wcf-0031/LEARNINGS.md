# Learnings
- 2026-11-04 [decision] — `LOG.md` is read from the checkout with a new `ProjectClone.read`, not `fetched_read`:
  `Git.output` runs git in text mode with `errors="replace"`, folding CRLF and replacing bytes that aren't UTF-8,
  which breaks "unchanged byte for byte". `read` and `write` use UTF-8 with `surrogateescape` and `newline=""`.
  Not handled: a global `core.autocrlf=input` still folds CRLF when `commit` runs `git add --all`, as for `close`.
- 2026-11-04 [decision] — `ProjectClone.write` now unlinks a link before writing. Without it, a `TURN` that is a
  link (which `task list` already reads as its target's name) made foundry write to the target, outside the clone.
  A linked or dir `LOG.md` is refused as "has no LOG.md", since `read` takes only regular files.
- 2026-11-04 [decision] — An empty `LOG.md` gets no newline before the entry's blank line: TASK.md's "a newline
  added first if the file didn't end with one" reads as applying to a file with text, so the result starts "\n## 1".
- 2026-11-04 [decision] — Replaces the two `ProjectClone` entries above, at the human's call: no `read`, and
  `write` raises on a link rather than replacing it. `LOG.md` is read with `fetched_read`, so "byte for byte" holds
  for UTF-8 logs with LF line endings, which agents write. CRLF folds to LF and bytes that aren't UTF-8 become
  U+FFFD (`Git.output`'s text mode). A linked `TURN` or `LOG.md` is refused, naming the path, with nothing pushed.
- 2026-11-04 [review] — Anything foundry appends to a task's notes from outside its session, such as `foundry task turn` writing LOG.md, breaks agent-kit/AGENTS.md's claim that `pull --rebase` on agent-notes never conflicts. Before then, each file in a task's notes dir had only one writer at a time. Raised as R3.
