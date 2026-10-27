# Skills are copied from upstream and edited in place

Roles use skills from `mattpocock/skills`. They are copied into the kit rather than installed in each sandbox, so a skill change is reviewed like any kit change and nothing is fetched at launch. The foundry's adaptations are plain edits to the copies. `foundry skills update` merges upstream's changes since the commit each skill records, with git's three-way merge, leaving conflict markers where both sides changed a line.

## Considered options

- **Regenerating each skill from upstream plus a patch file and a lock file.** A patch fails as soon as upstream moves a nearby line.
- **A separate shell script for updates.** Replaced by the `foundry` command, with the rest of the shell code (ADR 0010).

Source: #5, #20.
