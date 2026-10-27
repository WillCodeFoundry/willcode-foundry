# The repo policy

Every project's GitHub repository must match the files in this dir: its rulesets, its `.github/CODEOWNERS`, and the `ci-gate` part of its `.github/workflows/ci.yml`. Why one policy, checked by comparison, is in [ADR 0002](../../docs/adr/0002-repo-policy-by-comparison.md).

## Checking

```console
$ uv run foundry repo check               # every project: 'conforms', or each deviation's diff; exit 1 if any
$ uv run foundry repo check tkt-store     # one project
$ uv run foundry repo check --fix         # first create or update the rulesets to match, then check
```

Anything different from the policy is a deviation, shown as a diff, even when harmless. When a project really needs to differ, change the policy. A project GitHub refuses prints its error, and the rest are still checked.

`check` uses `gh` signed in as you, with admin rights on the repositories, never the agents' credentials. Rulesets on private repositories need GitHub Pro or Team.

## The files

| File | Holds | `--fix` writes it |
|---|---|---|
| `rulesets.yaml` | The rulesets, in the shape of GitHub's REST API. | yes |
| `CODEOWNERS` | Every project's `.github/CODEOWNERS`, word for word: you own every file. | no, the diff shows what to change |
| `ci-gate.yml` | The `on:` block and the `ci-gate` job every project's `ci.yml` must have. Copy it to start a project's CI. | no, the diff shows what to change |

## The rulesets

Repository admins (you) bypass them; the agents' users, with write access only, can't.

| Ruleset | Rule |
|---|---|
| `foundry-default-branch` | The default branch changes only through a reviewed pull request, with code-owner review and a passing `ci-gate`; no force-push or deletion. |
| `foundry-agent-branches` | `task/**` and `agent-notes` take signed commits only, and are never force-pushed or deleted. |
| `foundry-other-branches` | No other branch can be created, pushed or deleted, except by an admin, and by Dependabot under `dependabot/**`. |
| `foundry-tags` | Only admins create, move or delete tags. |

`ci-gate` ends each project's CI and fails if any other job did, so each project keeps its own jobs while the rulesets require one check. Its `needs` must name every other job; the template says `<all other jobs>`.

Code-owner review makes every change yours to approve. The agents' users, the reviewer role's included, have write access, so a plain required approval could come from an agent. It also covers a pull request that edits `ci.yml` to make `ci-gate` pass.

## What `check` ignores

Rulesets are matched by name, and fields GitHub adds are ignored. Extra items in a list, such as another bypass actor, still show. Rulesets the policy doesn't name are left alone: rulesets add up, so an extra one can't weaken these.

This repository is one of its own projects, and a test checks it conforms to this policy.
