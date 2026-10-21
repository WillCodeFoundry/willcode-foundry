# willcode-foundry

One instance of a willcode foundry: the configuration, role definitions, memory and launcher for a set of coding agents working on a group of projects. It holds no project code. Each agent runs in a Docker Sandbox, clones its project from GitHub, and hands work back by pushing branches.

## Use

```console
$ uv sync
$ uv run foundry run tkt-store dev WCF-0042          # start the dev role on task WCF-0042
$ uv run foundry run tkt-store planner               # roles without a task
$ uv run foundry run sessions/20261021-163005-dev-tkt-store-wcf-0042/   # re-run a session as it was
$ uv run foundry run tkt-store dev WCF-0042 --new    # replace the sandbox
$ uv run foundry run tkt-store dev WCF-0042 -- --continue              # args after -- go to the agent
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
│   │   └── hook-rules            # lists every rule the hooks enforce
│   ├── claude/
│   │   ├── managed-settings.json # Claude Code policy: only these hooks and permissions apply
│   │   └── hooks/                # guard-bash (PreToolUse), session-check (Stop)
│   ├── git/
│   │   ├── gitconfig             # behaviour shared by every role (pull.rebase, push.default, ...)
│   │   └── allowed_signers       # one line per signing role, for verifying commits
│   ├── hooks/                    # git hooks; core.hooksPath points here
│   │   ├── pre-commit, pre-push
│   │   └── lib/                  # the rules, one script per checkout/event
│   ├── roles/<role>/
│   │   ├── ROLE.md               # identity, method, definition of done, boundaries
│   │   ├── gitconfig             # name, email, key::signing key; includes ../../git/gitconfig
│   │   ├── memory/               # curated knowledge, one file per topic
│   │   └── init                  # optional role-specific setup, run by session-init
│   └── skills/<name>/SKILL.md    # reusable procedures
├── secrets/                      # untracked except .gitkeep
│   ├── ssh/<role>, <role>.pub
│   └── github/<role>.token       # optional
└── sessions/                     # untracked, written only by the launcher
    └── <YYYYMMDD>-<HHMMSS>-<sandbox>/
        ├── sbxenv.yaml           # the sandbox definition; written once, never overwritten
        └── session.yaml          # role, task, project, timings, status; updated as it changes
```

| Folder | Written by | Tracked |
|---|---|---|
| `src/`, `tests/`, `config/` | You | Yes |
| `agent-kit/` | You, plus the harvest step for `memory/` | Yes |
| `secrets/` | You | No |
| `sessions/` | The launcher | No |

## How a session runs

1. `foundry run PROJECT ROLE [TASK]` looks both up in `config/foundry.yaml`, names the sandbox `<role>-<project>-<task>` (stable, so a rerun re-attaches) and the session `<date>-<time>-<sandbox>`, and writes `sessions/<session>/sbxenv.yaml` and `session.yaml`. sbx requires a primary workspace, so the environment file names an empty temporary directory (recreated if the OS clears it); nothing is put in it. The only real mount is `agent-kit/`, read-only, and the `env` block carries `AGENT_ROLE`, `AGENT_TASK`, `AGENT_KIT_DIR`, `AGENT_REPO_URL`, `AGENT_PROJECT_DIR`, `AGENT_NOTES_DIR`.
2. `foundry.agent_sandbox` starts a private `ssh-agent` for the sandbox holding only `secrets/ssh/<role>`, creates the sandbox from the file (`sbx env create`), allows `github.com:22`, seeds GitHub's host keys, sets or clears the `github` secret, and checks from inside that the sandbox sees exactly that one key.
3. It runs `agent-kit/bin/session-init` inside the sandbox (`sbx env exec`), which clones `$AGENT_REPO_URL` into `$AGENT_PROJECT_DIR`, checks out `task/$AGENT_TASK`, adds the `agent-notes` worktree, points `core.hooksPath` at the kit, includes the role's `gitconfig`, runs the role's `init` if present, then `session-harden`s: installs Claude's managed settings and removes sudo. The launch aborts if any step fails.
4. `sbx env run` attaches the agent. It works per `AGENTS.md` and its `ROLE.md`, committing code to `task/<task>` and notes to `agent-notes`, pushing both.
5. The launcher replaces itself with `sbx`, so it never learns how the session ended: `session.yaml` records only what is known at creation, with `status: created`. Harvest (not yet built) will record the outcome. It reads `LEARNINGS.md` from `agent-notes` and files cross-project lessons into the role's `memory/`.

Preconditions the launcher does not create: the task branch `task/<task>` and a skeleton `.agent/<task>/TASK.md` on `agent-notes` must already exist on GitHub.

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
$ uv run ruff check . && uv run mypy
```

## sbx requirements

SSH agent forwarding must be on and not pinned to a fixed socket:

```console
$ sbx settings set ssh.agentForwardingEnabled true
$ sbx settings unset ssh.agentSocketPath
$ sbx daemon restart
```

The launcher passes `--auto-approve` to `sbx env create`, `run` and `rm`, approving each environment plan on your behalf; the plans mount only `agent-kit/` read-only and an empty directory, with no host commands. `sbx env` is marked experimental by Docker; the file format is isolated in `session.env_document` so a change there is one edit.

## Where agent output lives

Agents write nothing to this repository. Their work goes to the project repository on two branches:

| Branch | Holds | Written by |
|---|---|---|
| `task/<task-id>` | Code and project documentation | dev, qa |
| `agent-notes` | `.agent/<task-id>/TASK.md`, `PROGRESS.md`, `LEARNINGS.md`, `TASK.proposed.md` | all roles, each only in its own task folder |

`TASK.md` is owned by the human. The planner, the one interactive role, improves it by writing `TASK.proposed.md` for the human to apply.
