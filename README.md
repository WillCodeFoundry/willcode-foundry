# willcode-foundry

One instance of a willcode foundry: the configuration, role definitions, memory and launcher for a set of coding agents working on a group of projects. It holds no project code. Each agent runs in a Docker Sandbox, clones its project from GitHub, and hands work back by pushing branches.

## Use

```console
$ uv sync
$ uv run foundry task create tkt-store WCF-0042            # create the task: its branch, and its notes from config/task-template/
$ uv run foundry run tkt-store dev WCF-0042                # start the dev role on task WCF-0042, or re-attach
$ uv run foundry prune                                     # kill the ssh-agents of stopped or removed sandboxes
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
│   ├── repo-policy/              # what every project's repository must match (foundry repo check)
│   │   ├── rulesets.yaml         # GitHub rulesets, in the REST API's shape
│   │   ├── CODEOWNERS            # the project's .github/CODEOWNERS, verbatim
│   │   └── ci-gate.yml           # the on: block and ci-gate job its ci.yml must have
│   └── task-template/            # what a new task's .agent/<task>/ starts with (foundry task create)
│       ├── TASK.md               # the skeleton the human, or the planner's TASK.proposed.md, fills in
│       ├── PROGRESS.md           # the sections AGENTS.md requires
│       └── LEARNINGS.md
├── agent-kit/                    # everything an agent is given (read-only mount)
│   ├── AGENTS.md                 # instructions shared by every role
│   ├── bin/
│   │   ├── session-init          # clones the project, sets up checkouts, hooks, identity; runs hardening
│   │   ├── session-harden        # root step: installs Claude's managed settings; removes sudo and su; makes the Docker socket root-only
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
        └── workspace/            # the empty primary workspace sbx requires; nothing goes in it
```

| Folder | Written by | Tracked |
|---|---|---|
| `src/`, `tests/`, `config/` | You | Yes |
| `agent-kit/` | You, plus the harvest step for `memory/` | Yes |
| `secrets/` | You | No |
| `sessions/` | The launcher | No |

## How a session runs

The words used here, and in the code:

| Term | Means |
|---|---|
| **project** | A repository agents work on, listed in `config/foundry.yaml` |
| **role**, **task** | Who the agent is (`agent-kit/roles/<role>/`), and the work it's given (`task/<task>` and its `TASK.md`) |
| **sandbox** | The sbx environment for one role, project and task |
| **sandbox definition** | `sbxenv.yaml`, written once; what sbx creates the sandbox from |
| **session** | The host directory `sessions/<sandbox>/`: the sandbox definition and the empty workspace |
| **launch** | One attempt to start or re-attach to a sandbox |
| **repo policy** | What every project's GitHub repository must match: rulesets, CODEOWNERS, the `ci-gate` section of `ci.yml` |
| **deviation** | One way a repository differs from the repo policy, with its diff |
| **ruleset change** | One ruleset `foundry repo check --fix` created or updated |
| **GitHub**, **GhCli** | The interface foundry needs from GitHub (read rulesets and files, create and update rulesets), and that implemented through the `gh` command line, signed in as you |
| **GitClone** | A shallow clone of a project's repository in a scratch directory, made with git and your own access: lists its branches, fetches the ones needed one commit deep, commits and pushes |

1. `foundry run PROJECT ROLE TASK` looks the project and role up in `config/foundry.yaml` and names the sandbox `<role>-<project>-<task>`. The first time, it creates the session: the sandbox definition, `sessions/<sandbox>/sbxenv.yaml`, and the empty `sessions/<sandbox>/workspace/` that sbx requires as the primary workspace, though nothing is put in it. Later launches reuse the definition and re-attach, since sbx fixes a sandbox's mounts when it is created. A launch whose role, task or repository differs from the existing definition's is refused, since two of them can slug to one sandbox name. The launcher never removes a sandbox: to start one over, remove it yourself with `sbx env rm --force sessions/<sandbox>`, then delete `sessions/<sandbox>/`; its ssh-agent is stopped by the next launch (step 2). The only real mount is `agent-kit/`, read-only, and its variables are `AGENT_ROLE`, `AGENT_TASK`, `AGENT_KIT_DIR`, `AGENT_REPO_URL`, `AGENT_PROJECT_DIR`, `AGENT_NOTES_DIR`.
2. `foundry.agent_sandbox` first kills the ssh-agents of sandboxes that are stopped or removed, as `foundry prune` does: it compares the agents it started (found by their command line, `ssh-agent -a /tmp/sbx-agents/<sandbox>.sock -s`) with `sbx ls --json`, and kills each whose sandbox is missing or `stopped`; one a launch prepared in the last 10 minutes is spared. An idle agent only holds a private key, and launching its sandbox again starts a new one; sbx lists every sandbox its user has, so another foundry instance's running sandboxes keep their agents. It then starts a private `ssh-agent` for the sandbox holding only `secrets/ssh/<role>`, creates the sandbox from its definition if it doesn't exist (`sbx env create`), allows `github.com:22`, seeds GitHub's host keys, and checks from inside that the sandbox sees exactly that one key. If `secrets/github/<role>.token` exists, sbx is told to read the token from it on the host (`sbx secret set --command`), so the launcher never handles the token itself; otherwise the `github` secret is cleared.
3. It runs `agent-kit/bin/session-init` inside the sandbox (`sbx env exec`), which clones `$AGENT_REPO_URL` into `$AGENT_PROJECT_DIR`, checks out `task/$AGENT_TASK`, adds the `agent-notes` worktree, points `core.hooksPath` at the kit, includes the role's `gitconfig`, writes the agent's `~/.claude/CLAUDE.md` importing `AGENTS.md`, the role's `ROLE.md` and the task's `TASK.md` so the agent starts briefed, then `session-harden`s: installs Claude's managed settings and removes the agent's ways to root: sudo, `su` (root's password is locked) and Docker, whose daemon mounts the sandbox's own filesystem. sbx gives agent processes the `docker` group whatever `/etc/group` says, so the Docker socket is made root-only instead (`/etc/docker/daemon.json` sets its group to `root`, and the current socket is changed too), and `session-init` checks on every launch, with the agent's own groups, that it can't be used. The launch aborts if any step fails.
4. `sbx env run` attaches the agent, with permission prompts off (see [What protects what](#what-protects-what)). It works per `AGENTS.md` and its `ROLE.md`, committing code to `task/<task>` and notes to `agent-notes`, pushing both.
5. The launcher replaces itself with `sbx`, so it never learns how the session ended, or even whether the agent started. Harvest (not yet built) will record the outcome. It reads `LEARNINGS.md` from `agent-notes` and files cross-project lessons into the role's `memory/`.

Each command has a composition root that builds the real dependencies (`run.main`, `task.create_main`, `repo.check_main`) and a function that takes them as parameters (`run.prepare_launch`, `task.create`, `repo_policy.apply_rulesets` and `deviations`), which is what the tests call, with fakes for GitHub and the host's processes and no patching.

**Sessions created before the workspace moved into the session** point their definition at a temporary directory under `/tmp`. Once the OS clears it, launching one fails with `workspace '…' is not a directory`. Remove such a session and launch again: `sbx env rm --force sessions/<sandbox>`, then delete `sessions/<sandbox>/`.

Preconditions the launcher does not create: the task, which `foundry task create PROJECT TASK` creates in the project's repository, with git and your own access to it: the branch `task/<task>` from the default branch, and `.agent/<task>/` on `agent-notes`, a copy of `config/task-template/` (`TASK.md`, `PROGRESS.md`, `LEARNINGS.md`). Then write the task in its `TASK.md`, there or by applying the planner's `TASK.proposed.md`. The first task creates `agent-notes` as an orphan branch, sharing no history with the code. It refuses a task that already exists. Both branches are pushed together (`git push --atomic`), so a failure leaves neither.

## What protects what

Two kinds of control, and only the first is a boundary:

| Control | Enforced by | Holds against |
|---|---|---|
| Sandbox isolation, network policy, read-only `agent-kit/` mount | sbx / Docker | anything in the sandbox |
| Managed settings: permission mode, which hooks run, no attribution | root-owned file; `session-harden` removes sudo and `su`, and makes the Docker socket root-only | anything in the sandbox |
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

### Checking repositories against the repo policy

```console
$ uv run foundry repo check                       # every project: 'conforms', or each deviation's diff; exit 1 if any
$ uv run foundry repo check tkt-store             # one project
$ uv run foundry repo check --fix                 # first create or update the rulesets to match, then check
```

Every project's repository must match the repo policy in `config/repo-policy/`: its rulesets, its `.github/CODEOWNERS`, and the `ci-gate` section of its `.github/workflows/ci.yml`, which the rulesets depend on. `check` compares rather than analyses: anything different is a deviation, shown as a diff from the repository to the policy, even when it's harmless. A repository with none prints `conforms`. When a project really needs to differ, change the policy.

`rulesets.yaml` lists the rulesets, in the shape of GitHub's REST API; edit it, then run `check --fix`. Repository admins (you) bypass them; agents' users, with write access only, can't:

- `foundry-default-branch`: main changes only by a reviewed pull request whose `ci-gate` check passed, with code owner review; no force-push or deletion.
- `foundry-agent-branches`: `task/**` and `agent-notes` take signed commits only and are never force-pushed or deleted.
- `foundry-other-branches`: no other branch can be created, pushed or deleted, except by an admin, and Dependabot under `dependabot/**` (rulesets bind GitHub Apps too).
- `foundry-tags`: only admins create, move or delete tags.

Two of those rules rely on the project's own files, which `--fix` never writes; their diff shows what to change:

- **`ci.yml`** must have the `on:` block and the `ci-gate` job in `ci-gate.yml`, with `ci-gate`'s `needs` naming every other job (the template writes `<all other jobs>`). `ci-gate` ends the project's CI and fails if any other job did, so each project keeps its own jobs while the ruleset requires one check everywhere. To start a project's CI, copy `ci-gate.yml` into its `ci.yml`.
- **`CODEOWNERS`** must be `config/repo-policy/CODEOWNERS`, which names you for every file. Agents' users, the reviewer role's included, have write access, so a required approval alone could come from an agent; code owner review makes it yours. It also covers a pull request that changes `ci.yml` to make `ci-gate` pass, since a pull request runs the workflows it contains.

`check` matches rulesets by name and ignores fields GitHub adds; extra items in a list, such as another bypass actor, still show. Rulesets on GitHub that the policy doesn't name are left alone: rulesets add up, so an extra one can't weaken these. It uses the GitHub CLI signed in as you (`gh auth login`), with admin rights on the repositories; the agents' credentials are never used. Rulesets on private repositories need GitHub Pro or Team; on a free plan, GitHub refuses and `check` reports its message. This repository is one of its own projects, and a test checks it conforms to its own repo policy.

## The launcher

```
src/foundry/
├── cli.py              # `foundry` command; one subcommand per module in commands/
├── commands/run.py     # foundry run
├── commands/task.py    # foundry task create
├── commands/repo.py    # foundry repo check [--fix]
├── commands/prune.py   # foundry prune
├── repo_policy.py      # the repo policy: loads it, lists a repository's deviations, applies its rulesets
├── task.py             # creating a task: its branch, and its notes from the template (agent-notes, an orphan, is created by the first)
├── github.py           # the GitHub interface foundry needs, and GhCli: it through `gh api`, signed in as you
├── git_clone.py        # GitClone: a shallow scratch clone of a project's repository, through git
├── paths.py            # the only module that knows the instance layout; functions taking root
├── config.py           # loads and validates config/foundry.yaml
├── session.py          # sandbox naming and task ids, the definition's variables, creating a session
├── yaml_io.py          # YAML load with user-facing errors
├── errors.py
└── agent_sandbox/      # runs one sandbox safely; imports nothing from foundry (a test checks)
    ├── launcher.py     # LaunchRequest and launch(): the sequence in steps 2–3 above
    ├── pruning.py      # prune(): what stopped or removed sandboxes leave behind (their ssh-agents)
    ├── definition.py   # the sandbox definition: sbxenv.yaml, the only place that knows sbx's format
    ├── sbx.py          # sbx env create/exec/run, policy, known hosts, secrets
    ├── ssh_agent.py    # private agent, one key, fingerprint check; finding and killing foundry's agents
    ├── host.py         # the boundary to the host's processes: run, exec, environ, list and kill
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

These are the checks CI runs (`.github/workflows/ci.yml`), on the Python in `.python-version`, the oldest `requires-python` allows; CI also runs the tests on the newest. Its last job, `ci-gate`, passes only if every other job did, and is the check `config/repo-policy/rulesets.yaml` requires before a pull request can merge into main. Add a new job to `ci-gate`'s `needs`, or it won't block anything, and `foundry repo check` will show the deviation. Run ShellCheck from the repository root: the hooks' `source` directives are relative to it.

`tests/agent_kit/` tests the agent kit's scripts directly: `guard-bash` against commands it must allow and refuse, and the git hooks and Stop hook against a throwaway repository with a local origin. They need `git` and `bash`. `tests/test_task.py` likewise creates tasks in a throwaway bare repository, with `git`.

## sbx requirements

SSH agent forwarding must be on and not pinned to a fixed socket:

```console
$ sbx settings set ssh.agentForwardingEnabled true
$ sbx settings unset ssh.agentSocketPath
$ sbx daemon restart
```

The launcher passes `--auto-approve` to `sbx env create` and `run`, approving each sandbox plan on your behalf; the plans mount only `agent-kit/` read-only and an empty directory, with no host commands. `sbx env` is marked experimental by Docker; its file format is isolated in `agent_sandbox/definition.py` so a change there is one edit.

## Where agent output lives

Agents write nothing to this repository. Their work goes to the project repository on two branches:

| Branch | Holds | Written by |
|---|---|---|
| `task/<task-id>` | Code and project documentation | dev, qa |
| `agent-notes` | `.agent/<task-id>/TASK.md`, `PROGRESS.md`, `LEARNINGS.md`, `TASK.proposed.md` | all roles, each only in its own task folder |

`TASK.md` is owned by the human. The planner, the one interactive role, improves it by writing `TASK.proposed.md` for the human to apply.
