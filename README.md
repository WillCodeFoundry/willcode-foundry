# willcode-foundry

One instance of a willcode foundry: the configuration, role definitions, memory and launcher for a set of coding agents working on a group of projects. It holds no project code. Each agent runs in a Docker Sandbox, clones its project from GitHub, and hands work back by pushing branches.

## Use

```console
$ uv sync
$ uv run foundry run tkt-store dev WCF-0042                # start the dev role on task WCF-0042, or re-attach
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
│   ├── foundry.yaml              # instance name, projects (clone URLs), roles
│   └── project-standard/         # what every project's repository must match (foundry protect)
│       ├── rulesets.yaml         # GitHub rulesets, in the REST API's shape
│       ├── CODEOWNERS            # the project's .github/CODEOWNERS, verbatim
│       └── ci-gate.yml           # the on: block and ci-gate job its ci.yml must have
├── agent-kit/                    # everything an agent is given (read-only mount)
│   ├── AGENTS.md                 # instructions shared by every role
│   ├── bin/
│   │   ├── session-init          # clones the project, sets up checkouts, hooks, identity; runs hardening
│   │   ├── session-harden        # root step: installs Claude's managed settings; removes sudo, su and Docker
│   ├── claude/
│   │   ├── managed-settings.json # Claude Code policy: only these hooks and permissions apply
│   │   └── hooks/                # guard-bash (PreToolUse), session-check (Stop)
│   ├── git/
│   │   ├── gitconfig             # behaviour shared by every role (pull.rebase, push.default, ...)
│   │   └── allowed_signers       # one line per signing role, for verifying commits
│   ├── hooks/                    # git hooks; core.hooksPath points here
│   │   ├── pre-commit            # no task notes on the task branch; only this task's folder on agent-notes
│   │   ├── prepare-commit-msg    # adds the Task: trailer on the task branch
│   │   ├── pre-push              # only this task's branch and agent-notes
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
        └── session.yaml          # role, task, project, creation time, one entry per launch attempt
```

| Folder | Written by | Tracked |
|---|---|---|
| `src/`, `tests/`, `config/` | You | Yes |
| `agent-kit/` | You, plus the harvest step for `memory/` | Yes |
| `secrets/` | You | No |
| `sessions/` | The launcher | No |

## How a session runs

1. `foundry run PROJECT ROLE TASK` looks the project and role up in `config/foundry.yaml` and names the sandbox `<role>-<project>-<task>`. The first time, it writes `sessions/<sandbox>/sbxenv.yaml` and `session.yaml`; later runs reuse that file and re-attach, since sbx fixes a sandbox's mounts when it is created. The launcher never removes a sandbox: to start one over, remove it yourself with `sbx env rm sessions/<sandbox>`, then delete `sessions/<sandbox>/`. sbx requires a primary workspace, so the environment file names an empty temporary directory (recreated if the OS clears it); nothing is put in it. The only real mount is `agent-kit/`, read-only, and the `env` block carries `AGENT_ROLE`, `AGENT_TASK`, `AGENT_KIT_DIR`, `AGENT_REPO_URL`, `AGENT_PROJECT_DIR`, `AGENT_NOTES_DIR`.
2. `foundry.agent_sandbox` starts a private `ssh-agent` for the sandbox holding only `secrets/ssh/<role>`, creates the sandbox from the file if it doesn't exist (`sbx env create`), allows `github.com:22`, seeds GitHub's host keys, and checks from inside that the sandbox sees exactly that one key. If `secrets/github/<role>.token` exists, sbx is told to read the token from it on the host (`sbx secret set --command`), so the launcher never handles the token itself; otherwise the `github` secret is cleared.
3. It runs `agent-kit/bin/session-init` inside the sandbox (`sbx env exec`), which clones `$AGENT_REPO_URL` into `$AGENT_PROJECT_DIR`, checks out `task/$AGENT_TASK`, adds the `agent-notes` worktree, points `core.hooksPath` at the kit, includes the role's `gitconfig`, writes the agent's `~/.claude/CLAUDE.md` importing `AGENTS.md`, the role's `ROLE.md` and the task's `TASK.md` so the agent starts briefed, then `session-harden`s: installs Claude's managed settings and removes the agent's ways to root: sudo, `su` (root's password is locked) and Docker (the `docker` group, since the sandbox's Docker daemon mounts its own filesystem). The launch aborts if any step fails.
4. `sbx env run` attaches the agent, with permission prompts off (see [What protects what](#what-protects-what)). It works per `AGENTS.md` and its `ROLE.md`, committing code to `task/<task>` and notes to `agent-notes`, pushing both.
5. The launcher replaces itself with `sbx`, so it never learns how the session ended, or even whether the agent started: `session.yaml` records creation and each launch attempt, nothing more. Harvest (not yet built) will record the outcome. It reads `LEARNINGS.md` from `agent-notes` and files cross-project lessons into the role's `memory/`.

Preconditions the launcher does not create: the task branch `task/<task>` and a skeleton `.agent/<task>/TASK.md` on `agent-notes` must already exist on GitHub.

## What protects what

Two kinds of control, and only the first is a boundary:

| Control | Enforced by | Holds against |
|---|---|---|
| Sandbox isolation, network policy, read-only `agent-kit/` mount | sbx / Docker | anything in the sandbox |
| Managed settings: permission mode, which hooks run, no attribution | root-owned file; `session-harden` removes sudo, `su` and Docker | anything in the sandbox |
| One SSH key and token per role | the credentials' own scope on GitHub | anything in the sandbox |
| Which branches and tags may be pushed; no force-push or deletion; signed agent commits | the project's GitHub rulesets | anything with the role's credentials |
| Git hooks (`agent-kit/hooks/`) | git, via `core.hooksPath` | mistakes only |
| `guard-bash` (PreToolUse) | Claude Code, on Bash commands | mistakes only |
| `session-check` (Stop) | Claude Code, at end of turn | forgetting to commit or push |

The git hooks and `guard-bash` run inside the sandbox, so an agent that set out to skip them could: through a script, an alias, another language, or by editing `.git/config`. They only keep rules nothing else enforces, and explain the rule in the refusal:

- `pre-push`: push only `task/<this task>` and `agent-notes`. The rulesets allow any `task/**`, since GitHub can't tell one task from another.
- `pre-commit`: no task notes on the task branch; on `agent-notes`, only this task's `.agent/<task>/` folder, never its `TASK.md`.
- `prepare-commit-msg`: adds the `Task: <task>` trailer to commits on the task branch, so agents don't have to; `--no-verify` doesn't skip it.
- `guard-bash`: refuses `--no-verify` and any mention of `core.hooksPath`, which would skip or replace the hooks above.

Force-pushes, deletions, history rewrites and pushes elsewhere are left to the rulesets, which refuse them on the server. What must hold whatever the agent does belongs in the rows above the hooks.

### Checking projects against the standard

```console
$ uv run foundry protect check                    # every project; shows a diff for anything that differs, exit 1 if any
$ uv run foundry protect check tkt-store          # one project
$ uv run foundry protect apply                    # make the rulesets match, then check
```

Every project's repository must match the project standard in `config/project-standard/`: its rulesets, its `.github/CODEOWNERS`, and the part of its `.github/workflows/ci.yml` the rulesets depend on. `check` compares rather than analyses: anything different is shown as a diff from the project to the standard, even when it's harmless. When a project really needs to differ, change the standard.

`rulesets.yaml` lists the rulesets, in the shape of GitHub's REST API; edit it, then `apply`. Repository admins (you) bypass them; agents' users, with write access only, can't:

- `foundry-default-branch`: main changes only by a reviewed pull request whose `ci-gate` check passed, with code owner review; no force-push or deletion.
- `foundry-agent-branches`: `task/**` and `agent-notes` take signed commits only and are never force-pushed or deleted.
- `foundry-other-branches`: no other branch can be created, pushed or deleted, except by an admin, and Dependabot under `dependabot/**` (rulesets bind GitHub Apps too).
- `foundry-tags`: only admins create, move or delete tags.

Two of those rules rely on the project's own files, which `apply` never writes; their diff shows what to change:

- **`ci.yml`** must have the `on:` block and the `ci-gate` job in `ci-gate.yml`, with `ci-gate`'s `needs` naming every other job (the template writes `<all other jobs>`). `ci-gate` ends the project's CI and fails if any other job did, so each project keeps its own jobs while the ruleset requires one check everywhere. To start a project's CI, copy `ci-gate.yml` into its `ci.yml`.
- **`CODEOWNERS`** must be `config/project-standard/CODEOWNERS`, which names you for every file. Agents' users, the reviewer role's included, have write access, so a required approval alone could come from an agent; code owner review makes it yours. It also covers a pull request that changes `ci.yml` to make `ci-gate` pass, since a pull request runs the workflows it contains.

`check` matches rulesets by name and ignores fields GitHub adds; extra items in a list, such as another bypass actor, still show. Rulesets on GitHub that the standard doesn't name are left alone: rulesets add up, so an extra one can't weaken these. Both commands use the GitHub CLI signed in as you (`gh auth login`), with admin rights on the repositories; the agents' credentials are never used. Rulesets on private repositories need GitHub Pro or Team; on a free plan, GitHub refuses and `check` reports its message. This repository is one of its own projects, and a test checks it meets the standard.

## The launcher

```
src/foundry/
├── cli.py              # `foundry` command; one subcommand per module in commands/
├── commands/run.py     # foundry run
├── commands/protect.py # foundry protect check|apply
├── standard.py         # the project standard: loads it, compares a repository with it
├── github.py           # GitHub's REST API through `gh api`, signed in as you
├── paths.py            # the only module that knows the instance layout; functions taking root
├── config.py           # loads and validates config/foundry.yaml
├── session.py          # sandbox/session naming, sbxenv.yaml, session.yaml
├── yaml_io.py          # YAML load with user-facing errors; atomic dump
├── errors.py
└── agent_sandbox/      # runs one sandbox safely; imports nothing from foundry
    ├── launch.py       # the sequence in step 2–3 above
    ├── sbx.py          # sbx env create/exec/run, policy, known hosts, secrets
    ├── ssh_agent.py    # private agent, one key, fingerprint check
    ├── host.py         # the boundary to the host: commands and filesystem checks
    └── github_keys.py  # GitHub's published host keys, pinned
```

`agent_sandbox` is the code lifted from the standalone `agent-sandbox` repo, minus the parts the foundry now owns (git identity, `--clone`). It could be moved back out unchanged.

Development:

```console
$ uv sync --group dev
$ uv run pytest
$ uv run ruff check . agent-kit/claude/hooks/guard-bash && uv run ruff format --check . agent-kit/claude/hooks/guard-bash
$ uv run mypy
$ shellcheck --severity=warning --external-sources agent-kit/bin/* agent-kit/hooks/pre-* agent-kit/hooks/prepare-commit-msg agent-kit/hooks/lib/common.sh agent-kit/claude/hooks/session-check
```

These are the checks CI runs (`.github/workflows/ci.yml`), on the Python in `.python-version`, the oldest `requires-python` allows; CI also runs the tests on the newest. Its last job, `ci-gate`, passes only if every other job did, and is the check `config/project-standard/rulesets.yaml` requires before a pull request can merge into main. Add a new job to `ci-gate`'s `needs`, or it won't block anything, and `foundry protect check` will show the difference. Run ShellCheck from the repository root: the hooks' `source` directives are relative to it.

`tests/agent_kit/` tests the agent kit's scripts directly: `guard-bash` against commands it must allow and refuse, and the git hooks and Stop hook against a throwaway repository with a local origin. They need `git` and `bash`.

## sbx requirements

SSH agent forwarding must be on and not pinned to a fixed socket:

```console
$ sbx settings set ssh.agentForwardingEnabled true
$ sbx settings unset ssh.agentSocketPath
$ sbx daemon restart
```

The launcher passes `--auto-approve` to `sbx env create` and `run`, approving each environment plan on your behalf; the plans mount only `agent-kit/` read-only and an empty directory, with no host commands. `sbx env` is marked experimental by Docker; the file format is isolated in `session.build_env_file` so a change there is one edit.

## Where agent output lives

Agents write nothing to this repository. Their work goes to the project repository on two branches:

| Branch | Holds | Written by |
|---|---|---|
| `task/<task-id>` | Code and project documentation | dev, qa |
| `agent-notes` | `.agent/<task-id>/TASK.md`, `PROGRESS.md`, `LEARNINGS.md`, `TASK.proposed.md` | all roles, each only in its own task folder |

`TASK.md` is owned by the human. The planner, the one interactive role, improves it by writing `TASK.proposed.md` for the human to apply.
