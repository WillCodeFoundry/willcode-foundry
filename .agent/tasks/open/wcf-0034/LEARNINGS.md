# Learnings
- 2026-11-09 [git] — `FetchedBranch.read_text` reads a symlink as its target's
  name (git stores a link as a blob of mode 120000), and `task list` depends on
  that; refusing links needs the mode from `ls-tree`.
