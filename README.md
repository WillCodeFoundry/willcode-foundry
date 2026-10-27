# willcode-foundry

One instance of a willcode foundry: the configuration, role definitions, memory and launcher for a set of coding agents working on a group of projects. It holds no project code. Each agent runs in a Docker Sandbox, clones its project from GitHub, and hands work back by pushing branches.

## Use

```console
$ uv sync
$ uv run foundry task create tkt-store wcf-0042            # create the task: its branch, and its notes from config/task-template/
$ uv run foundry run tkt-store dev wcf-0042                # start the dev role on task wcf-0042, or re-attach
$ uv run foundry prune                                     # kill the ssh-agents of stopped or removed sandboxes
$ uv run foundry skills update                            # merge upstream's changes into the agent kit's copied skills
```

`uv tool install --editable .` puts `foundry` on your PATH so `uv run` can be dropped. Projects and roles must be listed in `config/foundry.yaml`, and every role listed must have its folder in `agent-kit/roles/<role>/`, holding its `ROLE.md` and `gitconfig`: foundry refuses to run any command otherwise; the SSH key for a role is `secrets/ssh/<role>`, and a GitHub token, if the role should have `gh`, is `secrets/github/<role>.token`. The dev opens pull requests with `gh`, so `secrets/github/dev.token` must exist and allow creating pull requests on each project.

## Layout

```
.
├── pyproject.toml                # the `foundry` package and command
├── src/foundry/                  # launcher code (see below)
├── src/agent_runtime/            # the code that runs inside a sandbox, around the agent (see below)
├── tests/
├── config/
│   ├── foundry.yaml              # instance name, projects (clone URLs), roles
│   ├── repo-policy/              # what every project's repository must match (foundry repo check)
│   │   ├── rulesets.yaml         # GitHub rulesets, in the REST API's shape
│   │   ├── CODEOWNERS            # the project's .github/CODEOWNERS, verbatim
│   │   └── ci-gate.yml           # the on: block and ci-gate job its ci.yml must have
│   └── task-template/            # what a new task's .agent/<task>/ starts with (foundry task create)
│       ├── TASK.md               # the skeleton the planner fills in once you approve its draft, or you do
│       ├── PROGRESS.md           # the sections AGENTS.md requires
│       └── LEARNINGS.md
├── agent-kit/                    # everything an agent is given (read-only mount)
│   ├── AGENTS.md                 # instructions shared by every role
│   ├── .build/
│   │   └── agent_runtime.pyz     # src/agent_runtime/, built here at every launch; untracked
│   ├── claude/
│   │   └── managed-settings.json # Claude Code policy: only these hooks and permissions apply; they run the runtime
│   ├── git/
│   │   ├── gitconfig             # behaviour shared by every role (pull.rebase, push.default, ...)
│   │   └── allowed_signers       # one line per signing role, for verifying commits
│   ├── hooks/                    # git hooks; core.hooksPath points here. Stubs calling agent_runtime.git_hooks
│   │   ├── pre-commit            # no task notes on the task branch; only this task's folder on agent-notes
│   │   ├── prepare-commit-msg    # adds the Task: trailer on the task branch
│   │   └── pre-push              # only this task's branch and agent-notes
│   ├── roles/<role>/
│   │   ├── ROLE.md               # identity, method, definition of done, boundaries
│   │   ├── gitconfig             # name, email, key::signing key; includes ../../git/gitconfig
│   │   ├── memory/               # curated knowledge, one file per topic
│   │   └── skills/<name>         # a link to each of the role's skills (../../../skills/<name>)
│   └── skills/
│       ├── LICENSE-mattpocock    # copied from the source repository at that commit
│       ├── git-conventions/      # the foundry's own skill: commit messages and pull request titles
│       └── tdd/, codebase-design/, …  # copied from upstream, edited in place for the foundry
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
| `agent-kit/` | You, plus the harvest step for `memory/` | Yes, except `.build/`, which the launcher writes |
| `secrets/` | You | No |
| `sessions/` | The launcher | No |

## How a session runs

The words used here, and in the code:

| Term | Means |
|---|---|
| **project** | A repository agents work on, listed in `config/foundry.yaml` |
| **role**, **task** | Who the agent is (`agent-kit/roles/<role>/`), and the work it's given: its branch `task/<task>` and its task notes, which always include its `TASK.md` |
| **task notes** | A task's own folder on `agent-notes`, `.agent/<task>/`: its `TASK.md`, written by you, or by the planner once you approve its draft, and what every role working on the task records there, each only in its own task's folder |
| **notes root** | `.agent/` on `agent-notes`, where every task's notes sit; nothing under it belongs on a task branch |
| **sandbox** | The sbx environment for one role, project and task |
| **sandbox definition** | `sbxenv.yaml`, written once; what sbx creates the sandbox from |
| **session** | The host-side record of one sandbox: its sandbox definition and the session variables in it, kept in its session directory |
| **session directory** | `sessions/<sandbox>/`: the sandbox definition and the empty workspace sbx requires |
| **session variables** | The `AGENT_*` variables a sandbox is created with, from `SessionVariables`: its role, task, repository, checkouts and the task's names. They tell the agent kit and the agent everything about the task, and never change afterwards |
| **launch** | One attempt to start or re-attach to a sandbox |
| **repo policy** | What every project's GitHub repository must match: rulesets, CODEOWNERS, the `ci-gate` section of `ci.yml` |
| **deviation** | One way a repository differs from the repo policy, with its diff |
| **ruleset change** | One ruleset `foundry repo check --fix` created or updated |
| **GitHub**, **GhCli** | The interface foundry needs from GitHub (read rulesets and files, create and update rulesets), and that implemented through the `gh` command line, signed in as you |
| **GitClone** | A shallow clone of a project's repository in a folder you give it, made with git and your own access: lists the remote's branches, checks one out (starting it empty if it doesn't exist), writes and commits files, signing each with SSH and your `user.signingkey`, and pushes branches together |

1. `foundry run PROJECT ROLE TASK` looks the project and role up in `config/foundry.yaml` and names the sandbox `<role>-<project>-<task>`. The first time, it creates the session: the sandbox definition, `sessions/<sandbox>/sbxenv.yaml`, and the empty `sessions/<sandbox>/workspace/` that sbx requires as the primary workspace, though nothing is put in it. A session a stopped launch left without its definition is finished if it holds only an empty `workspace/`, and refused otherwise. Later launches reuse the definition and re-attach, since sbx fixes a sandbox's mounts when it is created. A launch whose role, task or repository differs from the existing definition's is refused, since two of them can slug to one sandbox name, and so is a sandbox whose session variables this foundry would no longer set: one created before a variable was added or renamed, whose kit would use the old names. The launcher never removes a sandbox: to start one over, remove it yourself with `sbx env rm --force sessions/<sandbox>`, then delete `sessions/<sandbox>/`; its ssh-agent is stopped by the next launch (step 2). The only real mount is `agent-kit/`, read-only. At every launch, the launcher builds `src/agent_runtime/` into that kit's `.build/agent_runtime.pyz`, the kit the sandbox definition records, so a moved foundry still updates the kit its sandboxes mount; the archive is renamed over the old one, so a running sandbox never sees half of it, and a failed build aborts the launch. The session variables, named once in `agent_runtime.contract`, are `AGENT_ROLE`, `AGENT_TASK`, `AGENT_KIT_DIR`, `AGENT_REPO_URL`, `AGENT_PROJECT_DIR`, `AGENT_NOTES_DIR`, and the task's names from `Task`: `AGENT_TASK_BRANCH`, `AGENT_NOTES_BRANCH`, `AGENT_NOTES_ROOT`, `AGENT_TASK_NOTES`, `AGENT_TASK_FILE`, so the kit and its instructions spell none of them out.
2. `foundry.agent_sandbox` first kills the ssh-agents of sandboxes that are stopped or removed, as `foundry prune` does: it compares the agents it started (found by their command line, `ssh-agent -a /tmp/sbx-agents/<sandbox>.sock -s`) with `sbx ls --json`, and kills each whose sandbox is missing or `stopped`; one a launch prepared in the last 10 minutes is spared. An idle agent only holds a private key, and launching its sandbox again starts a new one; sbx lists every sandbox its user has, so another foundry instance's running sandboxes keep their agents. It then starts a private `ssh-agent` for the sandbox holding only `secrets/ssh/<role>`, creates the sandbox from its definition if it doesn't exist (`sbx env create`), allows `github.com:22`, seeds GitHub's host keys, and checks from inside that the sandbox sees exactly that one key. If `secrets/github/<role>.token` exists, sbx is told to read the token from it on the host (`sbx secret set --command`), so the launcher never handles the token itself; otherwise the `github` secret is cleared.
3. It runs the runtime's `session-init` inside the sandbox (`sbx env exec`, as `/usr/bin/python3 -I agent-kit/.build/agent_runtime.pyz session-init`), which first runs `session-setup` as the agent user: it clones `$AGENT_REPO_URL` into `$AGENT_PROJECT_DIR`, checks out `task/$AGENT_TASK`, adds the `agent-notes` worktree, points `core.hooksPath` at the kit, includes the role's `gitconfig`, writes the agent's `~/.claude/CLAUDE.md` importing `AGENTS.md`, the role's `ROLE.md` and the task's `TASK.md` so the agent starts briefed, links the role's `skills/` folder as `~/.claude/skills` (see [Skills](#skills)). On the first launch, `session-init` then runs `harden` as root, through sudo, given only `AGENT_KIT_DIR`: it installs Claude's managed settings and removes the agent's ways to root: sudo, `su` (root's password is locked) and Docker, whose daemon mounts the sandbox's own filesystem. sbx gives agent processes the `docker` group whatever `/etc/group` says, so the Docker socket is made root-only instead (`/etc/docker/daemon.json` sets its group to `root`, and the current socket is changed too). On every launch, `session-init` then runs `harden --verify` as the agent, with the groups sbx gives it: it checks that the agent can't run sudo, can't `su` to root, can't write to the Docker socket, that the managed settings are root-owned, read-only and the same as `agent-kit/claude/managed-settings.json`, that it can't write anywhere in the agent kit, which proves the mount is read-only, and that `/usr/bin/python3` resolves to a root-owned file it can't write, since every hook runs it. A sandbox that fails any check doesn't start the agent, naming every check it failed; one hardened by an older kit needs recreating. The launch aborts if any step fails.
4. `sbx env run` attaches the agent, with permission prompts off (see [What protects what](#what-protects-what)). It works per `AGENTS.md` and its `ROLE.md`, committing code to `task/<task>` and notes to `agent-notes`, pushing both.
5. The launcher replaces itself with `sbx`, so it never learns how the session ended, or even whether the agent started. Harvest (not yet built) will record the outcome. It reads `LEARNINGS.md` from `agent-notes` and files cross-project lessons into the role's `memory/`.

Each command has a composition root that builds the real dependencies (`run.main`, `task.create_main`, `repo.check_main`) and a function that takes them as parameters (`run.prepare_launch`, `task.create`, `repo_policy.check_project` and `fix_project`), which is what the tests call, with fakes for GitHub, the sandbox and the host's processes (`FakeGitHub` in `tests/test_repo_policy.py`, its only user, and fixtures in `tests/agent_sandbox/conftest.py`) and no patching.

**Sandboxes created before the agent runtime**, when the kit's code was bash scripts, have managed settings that run hooks which no longer exist, and `harden --verify` refuses them. Recreate every sandbox after updating to this version, as below.

**Sandboxes created with other session variables**, before one was added or renamed, are refused with the variables that differ. Recreate one as below: `sbx env rm --force sessions/<sandbox>`, then delete `sessions/<sandbox>/`, and launch again.

**Sessions created before the workspace moved into the session** point their definition at a temporary directory under `/tmp`. Once the OS clears it, launching one fails with `workspace '…' is not a directory`. Remove such a session and launch again: `sbx env rm --force sessions/<sandbox>`, then delete `sessions/<sandbox>/`.

Preconditions the launcher does not create: the task, which `foundry task create PROJECT TASK` creates in the project's repository, with git and your own access to it: the branch `task/<task>` from the default branch, and `.agent/<task>/` on `agent-notes`, a copy of `config/task-template/` (`TASK.md`, `PROGRESS.md`, `LEARNINGS.md`; a template without a `TASK.md` is refused). Task ids are lowercased, by `foundry task create` and `foundry run` alike: `WCF-0042` is task `wcf-0042`. Then write the task in its `TASK.md` yourself, or run the planner, which drafts it with you and writes it once you approve. The first task creates `agent-notes` as an orphan branch, sharing no history with the code. It refuses a task that already exists. Both branches are pushed together (`git push --atomic`), so a failure leaves neither.

## What protects what

Two kinds of control, and only the first is a boundary:

| Control | Enforced by | Holds against |
|---|---|---|
| Sandbox isolation, network policy, read-only `agent-kit/` mount | sbx / Docker | anything in the sandbox |
| Managed settings: permission mode, which hooks run, no attribution | root-owned file in a root-owned folder the agent can't write; `harden` removes sudo and `su`, and makes the Docker socket root-only; `harden --verify` checks all of it, as the agent, on every launch | anything in the sandbox |
| What the hooks and the launch run: `agent-kit/.build/agent_runtime.pyz`, on `/usr/bin/python3 -I` | the read-only mount, and the root-owned interpreter; `harden --verify` checks both | anything in the sandbox |
| One SSH key and token per role | the credentials' own scope on GitHub | anything in the sandbox |
| Which branches and tags may be pushed; no force-push or deletion; signed agent commits | the project's GitHub rulesets | anything with the role's credentials |
| Git hooks (`agent-kit/hooks/`) | git, via `core.hooksPath` | mistakes only |
| `guard-bash` (PreToolUse) | Claude Code, on Bash commands | mistakes only |
| `session-check` (Stop) | Claude Code, at end of turn | forgetting to commit or push |

The git hooks and `guard-bash` run inside the sandbox, so an agent that set out to skip them could: through a script, an alias, another language, or by editing `.git/config`. They only keep rules nothing else enforces, and explain the rule in the refusal:

- `pre-push`: push only `task/<this task>` and `agent-notes`. The rulesets allow any `task/**`, since GitHub can't tell one task from another.
- `pre-commit`: no task notes on the task branch (anything under `.agent/`); on `agent-notes`, only this task's `.agent/<task>/` folder.
- `prepare-commit-msg`: adds the `Task: <task>` trailer to commits on the task branch, so agents don't have to; `--no-verify` doesn't skip it.
- `guard-bash`: refuses `--no-verify` and any mention of `core.hooksPath`, which would skip or replace the hooks above.

Force-pushes, deletions, history rewrites and pushes elsewhere are left to the rulesets, which refuse them on the server. What must hold whatever the agent does belongs in the rows above the hooks.

The rows above rest on one rule: **code that managed settings reference, or that the launcher runs, lives in the agent kit**, and runs from its read-only mount. Managed settings fix which hook runs; a writable copy of its code would let the agent change what that hook does. So the runtime is never copied into the sandbox, and every call into it is `/usr/bin/python3 -I <kit>/.build/agent_runtime.pyz <command>`: the template's own interpreter, never `env python3`, which follows the agent's `PATH`, and `-I`, which ignores `PYTHONPATH`, `PYTHON*` variables and user site-packages, so the agent can't shadow the package. Managed settings find the kit through `$AGENT_KIT_DIR`, which sbx sets and the agent can't change for Claude Code's process. The git hooks' stubs find it from their own path instead: the agent sets the environment of its own `git` commands, and could otherwise point them at a runtime of its choosing. A stub that can't find the runtime fails, so git refuses the commit rather than skip the rule.

### Checking repositories against the repo policy

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

## The launcher

```
src/foundry/
├── cli.py              # `foundry` command; one subcommand per module in commands/
├── commands/run.py     # foundry run
├── commands/task.py    # foundry task create
├── commands/repo.py    # foundry repo check [--fix]
├── commands/prune.py   # foundry prune
├── commands/skills.py  # foundry skills update: merges upstream's changes into the kit's copied skills
├── runtime_build.py    # builds src/agent_runtime/ into a kit's .build/agent_runtime.pyz, atomically
├── repo_policy.py      # the repo policy: loads it, lists a repository's deviations, applies its rulesets
├── task.py             # Task: a task's id, branch and notes folder; creating one, its notes from the template (agent-notes, an orphan, is created by the first)
├── github.py           # the GitHub interface foundry needs, and GhCli: it through `gh api`, signed in as you
├── git_clone.py        # GitClone: a shallow clone of a project's repository, through git: check out, write, commit, push
├── paths.py            # the only module that knows the instance layout; functions taking root
├── config.py           # loads and validates config/foundry.yaml; Role: a role's SSH key and optional token
├── session.py          # open_or_create: names the sandbox, creates its session once, refuses a collision; SessionVariables
├── yaml_io.py          # YAML load with user-facing errors
├── errors.py
└── agent_sandbox/      # runs one sandbox safely; imports nothing from foundry (a test checks)
    ├── launcher.py     # LaunchRequest, launch() and prepare(): the sequence in steps 2–3 above, against the Sandbox port
    ├── pruning.py      # prune(): what stopped or removed sandboxes leave behind (their ssh-agents)
    ├── definition.py   # the sandbox definition: sbxenv.yaml, the only place that knows sbx's format
    ├── sandbox.py      # the Sandbox port, and SbxCli: it through sbx (env create/exec/run, policy, known hosts, secrets)
    ├── ssh_agent.py    # private agent, one key, fingerprint check; finding and killing foundry's agents
    ├── host.py         # the boundary to the host's processes: run, exec, environ, list and kill
    └── github_host_keys.py  # GitHub's published host keys, pinned
```

`agent_sandbox` is the code lifted from the standalone `agent-sandbox` repo, minus the parts the foundry now owns (git identity, `--clone`). It could be moved back out unchanged.

## The agent runtime

```
src/agent_runtime/        # runs inside a sandbox; the standard library only, never foundry or yaml (a test checks)
├── __main__.py           # checks the Python version first, then the commands below
├── contract.py           # the AGENT_* names, which foundry.session also uses; reading them back; how the runtime is called
├── session_init.py       # what the launcher runs: setup, hardening on the first launch, then the verify on every launch. Owns the handoff to root: the sudo probe, the root command, and the entries `harden` and `harden --verify` reach
├── session_setup.py      # the agent user's part: clones the project, sets up checkouts, hooks, identity, instructions
├── harden.py             # what each mode does, on a Machine: as root, installs Claude's managed settings, removes sudo and su, makes the Docker socket root-only; as the agent, checks it all
├── claude_hooks.py       # guard_bash (PreToolUse), session_check (Stop)
├── git_hooks.py          # pre_commit, prepare_commit_msg, pre_push, which agent-kit/hooks/ call, and their refusals
└── git.py                # git as the runtime reads a repository with: output captured; the current branch
```

| Command (`/usr/bin/python3 -I agent_runtime.pyz …`) | Run by |
|---|---|
| `session-init` | the launcher, as the agent, before the agent starts |
| `session-setup` | `session-init`; never needs root |
| `harden`, `harden --verify` | `session-init`: as root through sudo on the first launch, given `AGENT_KIT_DIR` alone; as the agent on every launch. Both enter through `session_init.root_mode` and `agent_mode` |
| `hook guard-bash`, `hook session-check` | Claude Code, from managed settings |

It targets the repository's Python floor, 3.11, like `foundry`, and the sandbox template ships a newer one, so the tests on CI's Python versions cover it. `__main__` still checks the version before importing anything else, so a template that someday ships an older `python3` fails at `session-init` with what it needs.

Development:

```console
$ uv sync --group dev
$ uv run pytest                  # the host tier: everything below but the two that follow; about 20 seconds
$ uv run pytest -m docker        # session-init in the sandbox's template image; needs a Docker daemon
$ uv run pytest -m sbx           # a real sbx sandbox, by hand: see Testing against real sbx
$ uv run ruff check . && uv run ruff format --check .
$ uv run mypy
```

`-m docker` and `-m sbx` fail, rather than skip, when what they need is missing, since you asked for them. Tests run as an ordinary user, never as root: root runs only inside the `docker` tier's containers.

| Folder | Covers | Runs |
|---|---|---|
| `tests/` (top level) | `foundry`: config, sessions, tasks, the runtime build, `foundry skills update`, repo policy | host tier |
| `tests/agent_sandbox/` | the launcher's sbx calls, against fakes of the host and sbx | host tier |
| `tests/agent_runtime/` | the runtime's functions, hardening on a modelled machine | host tier |
| `tests/agent_kit/` | the kit as delivered: the built pyz, hooks, `session-setup` and `session-init` | host tier |
| `tests/sandbox_image/` | `session-init` in containers from the sandbox's template image, as root inside them | `-m docker`; CI's `sandbox-image` job |
| `tests/sbx/` | a real sbx sandbox: launch, relaunch, restart | `-m sbx`, by hand |

These are the checks CI runs (`.github/workflows/ci.yml`), on the Python in `.python-version`, the oldest `requires-python` allows; CI also runs the host tier on the newest, and the `docker` tier as its `sandbox-image` job, on every pull request. The image is pinned by digest in `tests/sandbox_image/Dockerfile`, the only place it is named, and Dependabot bumps it. Its last job, `ci-gate`, passes only if every other job did, and is the check `config/repo-policy/rulesets.yaml` requires before a pull request can merge into main. Add a new job to `ci-gate`'s `needs`, or it won't block anything, and `foundry repo check` will show the deviation. The foundry has no shell scripts: the sandbox's code is `agent_runtime`, so ruff, mypy and pytest cover it too.

`tests/agent_runtime/` calls the runtime's functions directly: `guard_bash` against commands it must allow and refuse, and hardening through its two modes on a temporary machine (`harden.Machine`: its own settings, Docker files and sockets, interpreter, and stand-in `sudo`, `su` and `passwd`). One test runs root mode and then agent mode on the same files, as the first launch does; every way the agent could still reach root is a case that breaks one thing on a hardened machine and expects `verify` to refuse it; and root mode's refusals must leave the machine unchanged. The machine models the agent as neither owner nor in the group of what it touches, and who owns each path, since in a test root and the agent are one user. chmod of sudo and `passwd -l` run against stand-ins here; `tests/sandbox_image/` runs them for real. `tests/agent_kit/` tests the kit as delivered, with the runtime built into a copy of it once per run (the `built_kit` fixture in `tests/conftest.py`, so no test writes into `agent-kit/.build/`): the hooks' commands from managed settings as written, the git hooks through real `git commit` and `git push` against a throwaway repository with a local origin, the stubs in `agent-kit/hooks/` held to `contract.RUNTIME_PYZ` and to one another, `session-setup` through the pyz, `session-init` on a first launch and on a relaunch, where only `sudo` is a stand-in, alone on `PATH` with `git` so the machine's own `sudo` can't run (on the first launch it answers the probe and records the root command without running it; on a relaunch it is mode 0, as hardening leaves the real one), root mode without `AGENT_KIT_DIR`, root mode's refusal as sudo starts it, and that the pyz imports nothing outside the standard library. Only `sudo` is replaced: git, against a temporary origin, and the files under a throwaway `HOME` are real. They need `git`, and `/usr/bin/python3`, which the stubs and managed settings name. `tests/test_task.py` likewise creates tasks in a throwaway bare repository, with `git`. `tests/test_task_contract.py` checks that every `AGENT_*` variable the agent kit and runtime use is one the sandbox definition sets and one of them reads, and that `config/repo-policy/rulesets.yaml` names a task's branches as `task.py` does. The kit's tests take their variables from a real sandbox definition, through the `kit_env` fixture in `tests/agent_kit/conftest.py`.

`tests/sandbox_image/` runs `session-init` as the launcher does, as the agent, in containers from the template image sbx starts Claude Code sandboxes from (`docker/sandbox-templates:claude-code-docker`). Each container mounts a world-writable copy of the built kit read-only at its host path, as sbx does, and has a Docker socket the agent reaches only through a group added by number, as sbx gives it the docker group. The tests check the first launch hardens for real (settings root's, sudo and `su` gone, the socket closed, the kit unwritable), the relaunch only verifies, verify sees real permissions, and the mount, not file modes, protects the kit. They need Docker only through its command line.

### Testing against real sbx

`tests/sbx/` launches a real sbx sandbox, up to but not including attaching the agent, so Claude Code never starts. It shows what nothing else can: sbx accepts our sandbox definition, mounts the kit read-only at its host path, runs `session-init` as the agent with sudo the first time, and its private dockerd keeps the Docker socket root's after the sandbox restarts. It replaces launching a sandbox twice by hand.

- **Prerequisites:** sbx installed, with KVM, and `sbx login`; `secrets/ssh/dev` with access to `foundry-test`; and the task, created once with `uv run foundry task create foundry-test sbx-smoke`. The suite checks these before any sbx call, and fails listing every one missing.
- **The command:** `uv run pytest -m sbx`. No workflow runs it.
- **When:** after upgrading sbx, and before merging changes to `agent-kit/`, `src/agent_runtime/` or `src/foundry/agent_sandbox/`.
- **What it leaves:** nothing. It acts only on the sandbox `dev-foundry-test-sbx-smoke` and `sessions/dev-foundry-test-sbx-smoke/`, removing both before it starts and after it ends, whatever the outcome, then prunes ssh-agents as `foundry prune` does. Expect a few minutes, mostly creating the sandbox.

## Skills

Six of the agent kit's skills come from [mattpocock/skills](https://github.com/mattpocock/skills), by Matt Pocock, under the MIT licence: `tdd`, `codebase-design`, `domain-modeling`, `code-review`, `pr` and `grilling`. Each records in its `SKILL.md`'s frontmatter (`metadata.source`) where it came from: the upstream repository, its path there, the upstream commit it's up to date with, the author and the licence, whose text is `agent-kit/skills/LICENSE-mattpocock`. `pr` also keeps its own credit to Dex Horthy (Humanlayer) and its `CREDITS.md`. `git-conventions` is the foundry's own.

Each role's skills are links in `agent-kit/roles/<role>/skills/`, one per skill (`ls` it to see them); `session-setup` links that folder as the agent's `~/.claude/skills` at every launch, so Claude Code loads them as skills. To give a role a skill, `ln -s ../../../skills/<name> agent-kit/roles/<role>/skills/`; a test checks every link points at a skill, and that a role has every skill its skills call. They are adapted to how the foundry hands out work: through `TASK.md` on `agent-notes`, with only the planner talking to you, and review in rounds through `REVIEW.md`. The adaptations are edits to the copies themselves, so change a skill as you would any file in the kit.

- **To update,** by hand: `foundry skills update`, or `foundry skills update COMMIT` for a given upstream commit. For each skill with a `metadata.source`, it applies upstream's changes since the recorded commit, leaving out `agents/` (Codex-only metadata), with git's three-way merge, and records the new commit. Where upstream changed a line the foundry also changed, the file is left with conflict markers, as in any merge. Review with `git diff HEAD`, resolve, and commit.
- **To see everything the foundry changed in a skill:** after an update has fetched upstream's commit, `git diff <commit>:skills/engineering/tdd HEAD:agent-kit/skills/tdd`.
- **To copy another skill:** copy its folder from upstream without `agents/`, add a `metadata.source` block like the others', then edit it.

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
| `agent-notes` | `.agent/<task-id>/TASK.md`, `PROGRESS.md`, `LEARNINGS.md`, `REVIEW.md` | all roles, each only in its own task folder |

`TASK.md` is yours. The planner, the one interactive role, drafts it with you and writes it once you approve. Other roles must not change it; nothing stops them, so the reviewer checks its history and reports any change they made. Your commits on `agent-notes` are signed with SSH, as `agent-kit/git/allowed_signers` expects: admins bypass the rulesets, so nothing requires it, but the reviewer reports any unsigned change to `TASK.md` other than the one that created the task. `foundry task create` always signs the commit that creates the task, with SSH and your `user.signingkey`, and refuses to create the task if it can't. Name your key in your global git config; that alone turns signing on nowhere:

```console
$ git config --global user.signingkey ~/.ssh/id_ed25519.pub   # your line in allowed_signers; its private half in your ssh-agent
```

Then, in your own clone of the project's repository, where you commit to `agent-notes`, turn SSH signing on for that clone only:

```console
$ git config gpg.format ssh
$ git config commit.gpgsign true   # or sign one commit with git commit -S
```
