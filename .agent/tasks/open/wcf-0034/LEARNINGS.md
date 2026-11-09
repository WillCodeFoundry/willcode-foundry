# Learnings
- 2026-11-09 [git] — `FetchedBranch.read_text` reads a symlink as its target's
  name (git stores a link as a blob of mode 120000), and `task list` depends on
  that; refusing links needs the mode from `ls-tree`.
- 2026-11-09 [testing] — `counting_stand_in` finds the real command with
  `shutil.which` on the process's PATH, so in an end-to-end test it must be made
  after `enter_foundry` (which replaces PATH) and before its dir is prepended,
  or it finds itself.
- 2026-11-09 [git] — A link's target text can't leak through `FetchedBranch`:
  nothing is checked out, and `git show` of a mode-120000 blob gives only the
  target's name. So AC7's risk is the name, which `is_link` stops before
  `read_text`.
- 2026-11-09 [testing] — The unknown-project message lists every project in
  the foundry, so adding a project to a shared test foundry (`store_foundry`)
  changes that expected message.
