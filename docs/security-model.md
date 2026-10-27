# What protects what

Some controls hold whatever the agent does; the rest only stop mistakes. Why it is split this way is in [ADR 0001](adr/0001-github-enforces-hooks-only-guard.md).

## Boundaries and guardrails

| Control | Enforced by | Holds against |
|---|---|---|
| Sandbox isolation, network policy, read-only `agent-kit/` mount | sbx and Docker | anything in the sandbox |
| Managed settings: permission mode, which hooks run, no attribution | a root-owned file in a root-owned dir; hardening, checked as the agent on every launch | anything in the sandbox |
| The code the hooks and the launch run | the read-only mount, the root-owned link `/etc/claude-code/agent_runtime.pyz`, the root-owned `/usr/bin/python3` | anything in the sandbox |
| One SSH key and token per role | the credentials' own scope on GitHub | anything in the sandbox |
| Which branches and tags may be pushed; no force-push or deletion; signed agent commits | the project's GitHub rulesets ([repo policy](../config/repo-policy/README.md)) | anything with the role's credentials |
| Git hooks | git, through `core.hooksPath` | mistakes only |
| `guard-bash` | Claude Code, before each shell command | mistakes only |
| `session-check` | Claude Code, when the agent stops | forgetting to commit or push |

The agent runs with permission prompts off. What it may do is set by the rows above, not by asking you.

## The guardrails

The git hooks and `guard-bash` run inside the sandbox, so an agent set on getting past them can: through a script, an alias, or an edit to `.git/config`. They keep only rules nothing else enforces, and each refusal says what to do instead:

- **`pre-push`:** push only this task's branch and `agent-notes`. The rulesets allow any `task/**`, since GitHub can't tell one task from another.
- **`pre-commit`:** nothing under `.agent/` on the task branch; on `agent-notes`, only this task's dir.
- **`prepare-commit-msg`:** adds the `Task: <task>` trailer to commits on the task branch, even with `--no-verify`.
- **`guard-bash`:** refuses `--no-verify` and any mention of `core.hooksPath`, which would skip or replace the git hooks.
- **`session-check`:** blocks the stop while either checkout has work not committed or not pushed. It trusts the environment Claude Code gives it, which a settings file the agent writes can change.

Force-pushes, deletions, history rewrites and pushes elsewhere are left to the rulesets, which refuse them on the server.

## Keeping the agent from root

The agent's ways to root are sudo, `su` and Docker. Root mode closes each on the first launch ([ADR 0008](adr/0008-the-agent-cant-become-root.md)):

| Way to root | How root mode closes it |
|---|---|
| sudo | The binary `sudo` resolves to is made unusable. This is the last step, since it can't be undone: any earlier failure leaves sudo for the next launch to try again. |
| `su` | Root's password is locked. |
| Docker, whose daemon mounts the sandbox's own filesystem | The socket is made root-only, now and whenever dockerd restarts, through `/etc/docker/daemon.json`. sbx gives the agent the docker group by number, so leaving the group changes nothing. |

On every launch, agent mode checks as the agent that it can't use any of them, and that it can't change what protects against it:

- the managed settings and their dir belong to root, aren't writable, and match the kit's;
- every hook runs the runtime through the root-owned link, which points at the kit's runtime;
- nothing in the kit is writable, which proves the mount is read-only;
- every dir from `/` down to the kit belongs to root, so no other kit can be swapped in at its path;
- `/usr/bin/python3` belongs to root and isn't writable.

A sandbox that fails any check doesn't start the agent, and needs [recreating](../README.md#recreating-a-sandbox).

## The rule behind the rows

Code that the managed settings name, or that a launch runs, lives in the agent kit and runs from its read-only mount ([ADR 0010](adr/0010-runtime-from-the-read-only-kit.md)). Nothing finds it through an environment variable or `PATH`, because the agent sets both for Claude Code and for its own git.

## On your machine

- No secret and no sandbox definition may sit inside the kit, since the kit is mounted into every sandbox.
- foundry never reads a role's GitHub token: sbx reads it from the file, on your machine.
- Each sandbox's ssh-agent holds only its role's key, and the sandbox must see exactly that key ([ADR 0005](adr/0005-credentials-per-role.md)).
