# Skills

The agents' skills live in `agent-kit/skills/`. Six are copied from [mattpocock/skills](https://github.com/mattpocock/skills), by Matt Pocock, under the MIT licence: `tdd`, `codebase-design`, `domain-modeling`, `code-review`, `pr` and `grilling`. `git-conventions` is the foundry's own. Why they are copied rather than installed is in [ADR 0007](adr/0007-skills-copied-not-installed.md).

## Where each skill comes from

A copied skill records its source in its `SKILL.md` front matter, under `metadata.source`: the upstream repository, the path there, the commit it is up to date with, the author and the licence. The licence text is `agent-kit/skills/LICENSE-mattpocock-skills`. `pr` also keeps its credit to Dex Horthy (Humanlayer), in its `CREDITS.md`.

The copies are adapted to how the foundry hands out work: through `TASK.md` on `agent-notes`, with only the planner talking to you, and reviews in rounds in `REVIEW.md`. The adaptations are plain edits, so change a skill as you would any file in the kit.

## Which role has which skill

A role's skills are links in `agent-kit/roles/<role>/skills/`, one per skill. Each launch links that dir as the agent's `~/.claude/skills`, so Claude Code loads them as skills. To give a role a skill:

```console
$ ln -s ../../../skills/<name> agent-kit/roles/<role>/skills/
```

A test checks every link points at a skill, and that a role has every skill its skills call.

## Updating from upstream

```console
$ uv run foundry skills update            # to upstream's latest commit
$ uv run foundry skills update COMMIT     # to a given commit
$ git diff HEAD                           # review, resolve any conflicts, then commit
```

For each copied skill, the update applies upstream's changes since the recorded commit with git's three-way merge, then records the new commit. It leaves out `agents/`, which holds Codex-only metadata. Where upstream and the foundry changed the same line, the file is left with conflict markers, as in any merge.

The update stops before changing anything if a copied skill has uncommitted changes. A patch git rejects outright leaves that skill's recorded commit where it was, so the next run tries again.

To see everything the foundry changed in a skill, after an update has fetched upstream's commit:

```console
$ git diff <commit>:skills/engineering/tdd HEAD:agent-kit/skills/tdd
```

## Copying another skill

Copy its dir from upstream without `agents/`, add a `metadata.source` block like the others', then edit it.
