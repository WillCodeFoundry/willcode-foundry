# Every project matches one repo policy, checked by comparison

The rulesets of ADR 0001 only protect a project if every project has them, and has the files they rely on. So `config/repo-policy/` holds one policy: the rulesets, a `.github/CODEOWNERS` naming the owner for every file, and the `ci-gate` job every project's CI ends with. `foundry repo check` compares each repository with it: anything different is a deviation, shown as a diff, even when harmless. A project that needs to differ changes the policy.

The ruleset requires one check, `ci-gate`, instead of each project's own job names. Code-owner review makes the owner approve every change, since agents' users have write access and a plain required approval could come from an agent.

## Considered options

- **Analysing each repository** (workflow triggers, branch globs, CODEOWNERS rules). It reimplemented GitHub's own rules in about 390 lines, each a place to be subtly wrong.
- **Listing each project's job names in the ruleset.** The list would go stale.
- **Code owners for `.github/` only.** An agent could still approve a change that left `.github/` alone.

Source: #2, #18.
