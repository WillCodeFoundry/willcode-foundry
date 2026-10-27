# Checking repositories against the repo policy

```console
$ uv run foundry repo check                       # every project: 'conforms', or each deviation's diff; exit 1 if any
$ uv run foundry repo check tkt-store             # one project
$ uv run foundry repo check --fix                 # first create or update the rulesets to match, then check
```

Every project's repository must match the repo policy in `config/repo-policy/`: its rulesets, its `.github/CODEOWNERS`, and the `ci-gate` section of its `.github/workflows/ci.yml`, which the rulesets depend on. `check` compares rather than analyses: anything different is a deviation, shown as a diff from the repository to the policy, even when it's harmless. A repository with none prints `conforms`. A project GitHub refuses, or whose URL isn't GitHub's, prints its error, and the rest are still checked; with `--fix`, rulesets changed before the error are listed above it. When a project really needs to differ, change the policy.

`rulesets.yaml` lists the rulesets, in the shape of GitHub's REST API; edit it, then run `check --fix`. Repository admins (you) bypass them; agents' users, with write access only, can't:

- `foundry-default-branch`: main changes only by a reviewed pull request whose `ci-gate` check passed, with code owner review; no force-push or deletion.
- `foundry-agent-branches`: `task/**` and `agent-notes` take signed commits only and are never force-pushed or deleted.
- `foundry-other-branches`: no other branch can be created, pushed or deleted, except by an admin, and Dependabot under `dependabot/**` (rulesets bind GitHub Apps too).
- `foundry-tags`: only admins create, move or delete tags.

Two of those rules rely on the project's own files, which `--fix` never writes; their diff shows what to change:

- **`ci.yml`** must have the `on:` block and the `ci-gate` job in `ci-gate.yml`, with `ci-gate`'s `needs` naming every other job (the template writes `<all other jobs>`). `ci-gate` ends the project's CI and fails if any other job did, so each project keeps its own jobs while the ruleset requires one check everywhere. To start a project's CI, copy `ci-gate.yml` into its `ci.yml`.
- **`CODEOWNERS`** must be `config/repo-policy/CODEOWNERS`, which names you for every file. Agents' users, the reviewer role's included, have write access, so a required approval alone could come from an agent; code owner review makes it yours. It also covers a pull request that changes `ci.yml` to make `ci-gate` pass, since a pull request runs the workflows it contains.

`check` matches rulesets by name and ignores fields GitHub adds; extra items in a list, such as another bypass actor, still show. Rulesets on GitHub that the policy doesn't name are left alone: rulesets add up, so an extra one can't weaken these. It uses the GitHub CLI signed in as you (`gh auth login`), with admin rights on the repositories; the agents' credentials are never used. Rulesets on private repositories need GitHub Pro or Team; on a free plan, GitHub refuses and `check` reports its message. This repository is one of its own projects, and a test checks it conforms to its own repo policy.
