# What protects what

Two kinds of control, and only the first is a boundary:

| Control | Enforced by | Holds against |
|---|---|---|
| Sandbox isolation, network policy, read-only `agent-kit/` mount | sbx / Docker | anything in the sandbox |
| Managed settings: permission mode, which hooks run, no attribution | root-owned file in a root-owned folder the agent can't write; `harden` removes sudo and `su`, and makes the Docker socket root-only; `check-hardening` checks all of it, as the agent, on every launch | anything in the sandbox |
| What the hooks and the launch run: `agent-kit/.build/agent_runtime.pyz`, on `/usr/bin/python3 -IS`; the managed hooks through a root-owned link to it | the read-only mount, the root-owned link, and the root-owned interpreter; `check-hardening` checks all three | anything in the sandbox |
| One SSH key and token per role | the credentials' own scope on GitHub | anything in the sandbox |
| Which branches and tags may be pushed; no force-push or deletion; signed agent commits | the project's GitHub rulesets | anything with the role's credentials |
| Git hooks (`agent-kit/hooks/`) | git, via `core.hooksPath` | mistakes only |
| `guard-bash` (PreToolUse) | Claude Code, on Bash commands | mistakes only |
| `session-check` (Stop) | Claude Code, at end of turn; it trusts the environment Claude Code gives it, which a settings file the agent writes can change | forgetting to commit or push |

The git hooks and `guard-bash` run inside the sandbox, so an agent that set out to skip them could: through a script, an alias, another language, or by editing `.git/config`. They only keep rules nothing else enforces, and explain the rule in the refusal:

- `pre-push`: push only `task/<this task>` and `agent-notes`. The rulesets allow any `task/**`, since GitHub can't tell one task from another.
- `pre-commit`: no task notes on the task branch (anything under `.agent/`); on `agent-notes`, only this task's `.agent/<task>/` folder.
- `prepare-commit-msg`: adds the `Task: <task>` trailer to commits on the task branch, so agents don't have to; `--no-verify` doesn't skip it.
- `guard-bash`: refuses `--no-verify` and any mention of `core.hooksPath`, which would skip or replace the hooks above.

Force-pushes, deletions, history rewrites and pushes elsewhere are left to the rulesets, which refuse them on the server. What must hold whatever the agent does belongs in the rows above the hooks.

The rows above rest on one rule: **code that managed settings reference, or that the launcher runs, lives in the agent kit**, and runs from its read-only mount. Managed settings fix which hook runs; a writable copy of its code would let the agent change what that hook does. So the runtime is never copied into the sandbox, and every call into it is `/usr/bin/python3 -IS <kit>/.build/agent_runtime.pyz <command>`: the template's own interpreter, never `env python3`, which follows the agent's `PATH`, and `-IS`: `-I` ignores `PYTHONPATH`, `PYTHON*` variables and user site-packages, so the agent can't shadow the package, and `-S` skips `site`, so a `.pth` file in a site-packages folder can't run before it; the runtime needs only the standard library. Neither finds the runtime through `$AGENT_KIT_DIR`. Managed settings name `/etc/claude-code/agent_runtime.pyz`, a link root mode makes to the kit's runtime, beside the settings in their root-owned folder: a settings file the agent writes can set Claude Code's environment, so a hook command reading a variable would run whatever the agent pointed it at. The git hooks run it through the same link: each is a two-line `sh` stub, `exec /usr/bin/python3 -IS /etc/claude-code/agent_runtime.pyz git-hook <hook> "$@"`, since the agent sets the environment of its own `git` commands too. A non-interactive `sh` reads no startup file, and the stub names every path, so neither `PATH` nor `ENV` changes what it runs. Without the link, before hardening or after it was removed, Python can't open the runtime, and git refuses the commit rather than skip the rule.
