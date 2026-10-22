# willcode-foundry

One instance of a willcode foundry: the configuration, role definitions, memory and launcher for a set of coding agents working on a group of projects. It holds no project code. Each agent runs in a Docker Sandbox, clones its project from GitHub, and hands work back by pushing branches.

## Use

```console
$ uv sync
$ uv run foundry run tkt-store dev WCF-0042                # start the dev role on task WCF-0042, or re-attach
$ uv run foundry run tkt-store dev WCF-0042 --fresh        # replace the sandbox with a fresh one
$ uv run foundry run tkt-store dev WCF-0042 -- --continue  # args after -- go to the agent
```

`uv tool install --editable .` puts `foundry` on your PATH so `uv run` can be dropped. Projects and roles must be listed in `config/foundry.yaml`; the SSH key for a role is `secrets/ssh/<role>`, and a GitHub token, if the role should have `gh`, is `secrets/github/<role>.token`.

## Layout

```
.
├── pyproject.toml                # the `foundry` package and command
├── src/foundry/                  # launcher code (see below)
├── tests/
├── config/
│   └── foundry.yaml              # instance name, projects (clone URLs), roles
├── agent-kit/                    # everything an agent is given (read-only mount)
│   ├── AGENTS.md                 # instructions shared by every role
│   ├── bin/
│   │   ├── session-init          # clones the project, sets up checkouts, hooks, identity; runs hardening
│   │   ├── session-harden        # root step: installs Claude's managed settings, removes sudo
│   ├── claude/
│   │   ├── managed-settings.json # Claude Code policy: only these hooks and permissions apply
│   │   └── hooks/                # guard-bash (PreToolUse), session-check (Stop)
│   ├── git/
│   │   ├── gitconfig             # behaviour shared by every role (pull.rebase, push.default, ...)
│   │   └── allowed_signers       # one line per signing role, for verifying commits
│   ├── hooks/                    # git hooks; core.hooksPath points here
│   │   ├── pre-commit, commit-msg, pre-push   # each holds its own rules
│   │   └── lib/common.sh         # shared helpers
│   ├── roles/<role>/
│   │   ├── ROLE.md               # identity, method, definition of done, boundaries
│   │   ├── gitconfig             # name, email, key::signing key; includes ../../git/gitconfig
│   │   ├── memory/               # curated knowledge, one file per topic
│   └── skills/<name>/SKILL.md    # reusable procedures
├── secrets/                      # untracked except .gitkeep
│   ├── ssh/<role>, <role>.pub
│   └── github/<role>.token       # optional
└── sessions/                     # untracked, written only by the launcher
    └── <sandbox>/                # one per sandbox: <role>-<project>-<task>
        ├── sbxenv.yaml           # the sandbox definition; written once, never overwritten
        └── session.yaml          # role, task, project, creation time, one entry per launch
```

| Folder | Written by | Tracked |
|---|---|---|
| `src/`, `tests/`, `config/` | You | Yes |
| `agent-kit/` | You, plus the harvest step for `memory/` | Yes |
| `secrets/` | You | No |
| `sessions/` | The launcher | No |

## How a session runs

1. `foundry run PROJECT ROLE TASK` looks the project and role up in `config/foundry.yaml` and names the sandbox `<role>-<project>-<task>`. The first time, it writes `sessions/<sandbox>/sbxenv.yaml` and `session.yaml`; later runs reuse that file and re-attach, since sbx fixes a sandbox's mounts when it is created. sbx requires a primary workspace, so the environment file names an empty temporary directory (recreated if the OS clears it); nothing is put in it. The only real mount is `agent-kit/`, read-only, and the `env` block carries `AGENT_ROLE`, `AGENT_TASK`, `AGENT_KIT_DIR`, `AGENT_REPO_URL`, `AGENT_PROJECT_DIR`, `AGENT_NOTES_DIR`.
2. `foundry.agent_sandbox` starts a private `ssh-agent` for the sandbox holding only `secrets/ssh/<role>`, creates the sandbox from the file if it doesn't exist (`sbx env create`), allows `github.com:22`, seeds GitHub's host keys, and checks from inside that the sandbox sees exactly that one key. If `secrets/github/<role>.token` exists, sbx is told to read the token from it on the host (`sbx secret set --command`), so the launcher never handles the token itself; otherwise the `github` secret is cleared.
3. It runs `agent-kit/bin/session-init` inside the sandbox (`sbx env exec`), which clones `$AGENT_REPO_URL` into `$AGENT_PROJECT_DIR`, checks out `task/$AGENT_TASK`, adds the `agent-notes` worktree, points `core.hooksPath` at the kit, includes the role's `gitconfig`, writes the agent's `~/.claude/CLAUDE.md` importing `AGENTS.md`, the role's `ROLE.md` and the task's `TASK.md` so the agent starts briefed, then `session-harden`s: installs Claude's managed settings and removes sudo. The launch aborts if any step fails.
4. `sbx env run` attaches the agent, with permission prompts off (see [What protects what](#what-protects-what)). It works per `AGENTS.md` and its `ROLE.md`, committing code to `task/<task>` and notes to `agent-notes`, pushing both.
5. The launcher replaces itself with `sbx`, so it never learns how the session ended: `session.yaml` records creation and each launch, nothing more. Harvest (not yet built) will record the outcome. It reads `LEARNINGS.md` from `agent-notes` and files cross-project lessons into the role's `memory/`.

Preconditions the launcher does not create: the task branch `task/<task>` and a skeleton `.agent/<task>/TASK.md` on `agent-notes` must already exist on GitHub.

## What protects what

Two kinds of control, and only the first is a boundary:

| Control | Enforced by | Holds against |
|---|---|---|
| Sandbox isolation, network policy, read-only `agent-kit/` mount | sbx / Docker | anything in the sandbox |
| Managed settings: permission mode, which hooks run, no attribution | root-owned file; `session-harden` removes sudo | anything in the sandbox |
| One SSH key and token per role | the credentials' own scope on GitHub | anything in the sandbox |
| Which branches may be pushed; no force-push or deletion | the project's GitHub rules | anything with the role's credentials |
| Git hooks (`agent-kit/hooks/`) | git, via `core.hooksPath` | mistakes only |
| `guard-bash` (PreToolUse) | Claude Code, on Bash commands | mistakes only |
| `session-check` (Stop) | Claude Code, at end of turn | forgetting to commit or push |

The git hooks and `guard-bash` run inside the sandbox, so an agent that set out to skip them could: through a script, an alias, another language, or by editing `.git/config`. They exist to stop the common slips, such as reaching for `--no-verify` when a hook fails or force-pushing after a bad rebase, and to explain the rule in the refusal. What must hold whatever the agent does belongs in the rows above them, chiefly the project's GitHub rules.

## The launcher

```
src/foundry/
├── cli.py              # `foundry` command; one subcommand per module in commands/
├── commands/run.py     # foundry run
├── paths.py            # the only module that knows the instance layout; functions taking root
├── config.py           # loads and validates config/foundry.yaml
├── session.py          # sandbox/session naming, sbxenv.yaml, session.yaml
├── yaml_io.py          # YAML load with user-facing errors; atomic dump
├── errors.py
└── agent_sandbox/      # runs one sandbox safely; imports nothing from foundry
    ├── launch.py       # the sequence in step 2–3 above
    ├── sbx.py          # sbx env create/exec/run/rm, policy, known hosts, secrets
    ├── ssh_agent.py    # private agent, one key, fingerprint check
    ├── host.py         # the boundary to the host: commands and filesystem checks
    └── github_keys.py  # GitHub's published host keys, pinned
```

`agent_sandbox` is the code lifted from the standalone `agent-sandbox` repo, minus the parts the foundry now owns (git identity, `--clone`). It could be moved back out unchanged.

Development:

```console
$ uv sync --group dev
$ uv run pytest
$ uv run ruff check . && uv run ruff format --check . && uv run mypy
```

`tests/kit/` tests the kit's scripts directly: `guard-bash` against commands it must allow and refuse, and the git hooks and Stop hook against a throwaway repository with a local origin. They need `git` and `bash`.

## sbx requirements

SSH agent forwarding must be on and not pinned to a fixed socket:

```console
$ sbx settings set ssh.agentForwardingEnabled true
$ sbx settings unset ssh.agentSocketPath
$ sbx daemon restart
```

The launcher passes `--auto-approve` to `sbx env create`, `run` and `rm`, approving each environment plan on your behalf; the plans mount only `agent-kit/` read-only and an empty directory, with no host commands. `sbx env` is marked experimental by Docker; the file format is isolated in `session.build_env_file` so a change there is one edit.

## Where agent output lives

Agents write nothing to this repository. Their work goes to the project repository on two branches:

| Branch | Holds | Written by |
|---|---|---|
| `task/<task-id>` | Code and project documentation | dev, qa |
| `agent-notes` | `.agent/<task-id>/TASK.md`, `PROGRESS.md`, `LEARNINGS.md`, `TASK.proposed.md` | all roles, each only in its own task folder |

`TASK.md` is owned by the human. The planner, the one interactive role, improves it by writing `TASK.proposed.md` for the human to apply.
