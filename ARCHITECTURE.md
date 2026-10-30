# Architecture

How the foundry is put together, and the rules its code follows. The words are defined in [GLOSSARY.md](GLOSSARY.md); why things are this way is in [docs/adr/](docs/adr/README.md).

## Bird's-eye view

Three programs share this repository:

- **foundry** (`src/foundry/`) runs on your machine. It creates tasks in project repositories, writes each sandbox's definition once, builds the runtime into the agent kit, and hands the terminal to sbx.
- **The agent kit** (`agent-kit/`) is data, mounted read-only into every sandbox at the same path as on your machine: instructions, roles, skills, Claude Code's managed settings, the git hook stubs and the built runtime.
- **The runtime** (`src/agent_runtime/`) is built into `agent-kit/.build/agent_runtime.pyz` at every launch and runs inside the sandbox: setup, hardening and the hooks.

A launch, end to end:

1. `foundry run PROJECT [ROLE] TASK` reads the config, finds the task on `agent-notes`, opens or creates the session, and builds the runtime into the kit. It refuses a closed task, or one that doesn't exist. Without ROLE, it reads the task's `TURN` file too.
2. `foundry.agent_sandbox` prunes stale ssh-agents, starts this sandbox's own, and creates the sandbox if it doesn't exist. It allows SSH to GitHub, has sbx read the role's token from its file, and checks the sandbox sees exactly the role's key.
3. The runtime's `session-init` runs in the sandbox: setup as the agent, hardening as root on the first launch, then the check as the agent.
4. foundry replaces itself with `sbx run --name`, which attaches the agent and sends it the opening prompt. Only `sbx run` passes arguments to the agent; `sbx env run` reads them as more paths. foundry never learns how the agent run ended.

## Codemap

### foundry: `src/foundry/`

| Module | What it does |
|---|---|
| `cli.py` | The `foundry` command; it prints the errors foundry's code raises. |
| `commands/` | One module per subcommand: `run`, `task`, `repo`, `prune`, `skills`. Each builds its real dependencies in a composition root and passes them to the code that uses them, so the tests can pass fakes instead (design rule 7). |
| `session.py` | Names the sandbox, creates its session once, reads it back, and refuses one that no longer matches (`SessionVariables`). |
| `task.py` | `Task` and its `Status`: the one place a task's names are spelled, open and closed paths included. |
| `project_tasks.py` | `ProjectTasks`: finding a project's tasks by id, with the status their notes dir gives them; creating, closing and reopening them; reading a task's turn. |
| `project_clone.py` | `ProjectClone`: the throwaway clone `foundry task` commits and pushes from. |
| `runtime_build.py` | Builds the runtime into the kit, replacing it only when it changed. |
| `repo_policy.py`, `github.py` | `foundry repo check`: compares each project's repository with the repo policy, through `gh`. |
| `skills.py` | `foundry skills update`: merges upstream's changes into the copied skills. |
| `config.py`, `paths.py` | `config/foundry.yaml`, and where everything sits in this repository. |
| `agent_sandbox/` | Everything that talks to sbx, importing nothing else from foundry: the launch sequence (`launcher.py`), the sandbox definition's format (`definition.py`), sbx's command lines (`sandbox.py`), ssh-agents (`ssh_agent.py`, `pruning.py`), and the host's processes (`host.py`). |

### The runtime: `src/agent_runtime/`

| Module | What it does |
|---|---|
| `__main__.py` | The runtime's commands; it prints the errors the runtime's code raises. |
| `session_init.py` | `session-init`: setup, root mode through sudo on the first launch, then agent mode. |
| `session_setup.py` | The agent user's part: checkouts, git identity, the agent's instructions and skills. |
| `hardening.py` | Root mode and agent mode, each step beside the check that proves it, acting on a `Machine`. |
| `claude_hooks.py`, `git_hooks.py` | The Claude hooks and the git hooks. |
| `contract.py`, `agent_kit.py`, `git.py`, `atomic_files.py` | Shared with foundry: the session variables, the kit's layout, running git, replacing a file in one step. |

The runtime's commands, each run as `/usr/bin/python3 -IS agent_runtime.pyz <command>`:

| Command | Run by |
|---|---|
| `session-init` | foundry, as the agent, before the agent starts |
| `session-setup` | `session-init` runs it in-process; the command is for running setup alone, by hand or in tests |
| `harden` | `session-init`, as root through sudo, on the first launch |
| `check-hardening` | `session-init` runs agent mode in-process on every launch; the command runs it alone |
| `claude-hook guard-bash`, `claude-hook session-check` | Claude Code, from the managed settings |
| `git-hook pre-commit`, `git-hook prepare-commit-msg`, `git-hook pre-push` | git, from the stubs in `agent-kit/hooks/` |

The runtime targets Python 3.11, like foundry. `__main__.py` checks the version before importing anything, so an older interpreter fails with a message.

### Everything else

| Path | What it is |
|---|---|
| `agent-kit/` | What every agent is given; see the glossary's "Agent kit". |
| `config/` | `foundry.yaml` (projects and roles), the task template, and the [repo policy](config/repo-policy/README.md). |
| `sessions/`, `secrets/` | Untracked: one dir per sandbox, and each role's SSH key and optional token. |
| `tests/` | The host tier, plus `sandbox_image/` (`-m docker`) and `sbx/` (`-m sbx`); see [CONTRIBUTING.md](CONTRIBUTING.md). |

## Design rules

Follow these when changing the code. Each names what holds it today.

1. **One spelling per shared name.** A name or path used on both sides of a boundary is spelled in one module, and tests hold every other copy to it: the kit's layout in `agent_runtime/agent_kit.py`, the session variables in `agent_runtime/contract.py`, a task's names in `foundry/task.py`, which the rulesets must agree with. The hook stubs and the managed settings can't import anything, so they spell the runtime's link, held to it by tests. *Held by `tests/agent_runtime/test_agent_kit.py`, `tests/test_task_contract.py`, `tests/agent_kit/test_git_hook_command.py` and `tests/agent_kit/test_managed_settings.py`.*
2. **Programs meet only at named seams.** foundry imports four runtime modules and no others, plus the package itself to build it; the runtime imports only the standard library; `agent_sandbox` imports nothing else from foundry. *Held by `tests/test_runtime_boundary.py`, `tests/agent_kit/test_runtime.py` and `tests/agent_sandbox/test_boundary.py`.*
3. **One door to each outside system.** All git goes through `agent_runtime.git.Git`, GitHub through the `GitHub` protocol, `agent_sandbox`'s commands through `Host`, and sbx through `agent_sandbox`. Tests never patch: they fake `GitHub` and `Host`, run real git in temporary repositories, and put stand-ins for `sudo`, `su` and `passwd` on `PATH`. *Held by review.*
4. **Nothing the agent can change decides which code protects against it.** The runtime runs from the read-only kit, on `/usr/bin/python3 -IS`, and hooks find it only through the root-owned link, never an environment variable or `PATH`. Agent mode checks all of this as the agent on every launch. Guardrails may trust the agent's environment, since they only stop mistakes. See ADRs [0008](docs/adr/0008-the-agent-cant-become-root.md) and [0010](docs/adr/0010-runtime-from-the-read-only-kit.md). *Held by agent mode, `tests/agent_kit/` and the docker tier.*
5. **Never change what you can't recreate; refuse and explain.** foundry writes a sandbox's definition once and hardens it once, and never rewrites, re-hardens or removes it. Each launch refreshes only what is meant to change: the runtime, the agent's instructions and the token. A mismatch is refused, saying how to recreate the sandbox. See [ADR 0004](docs/adr/0004-sandboxes-are-immutable.md). *Held by `tests/test_session.py` and `tests/agent_sandbox/test_launcher.py`.*
6. **Fail fast, with a message; don't program defensively.** When something isn't as expected, stop and say what is wrong and how to fix it: don't retry, fall back to a default, or work around it. Handle only the failures that have happened or that the design expects. An exception's text is the message the user reads, and only entry points print it. Where the design expects failure, it says which way to fail: a hook that enforces a rule blocks when it can't check it, and a guardrail prefers a rare miss to a false refusal ([ADR 0001](docs/adr/0001-github-enforces-hooks-only-guard.md)). *Held by review; the printed messages by the tests.*
7. **A composition root only builds and passes.** A command's `main` builds the real config, clones, hosts and sandboxes, and passes them to the functions that use them. It decides nothing. Every check, and every choice of what to do, is in a function the tests call with their own clones and fakes. Logic in `main` is logic no test reaches. *Held by review.*
