# Architecture

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
│   ├── hooks/                    # git hooks; core.hooksPath points here. Two-line sh stubs, each exec'ing the runtime's git-hook command
│   │   ├── pre-commit            # no task notes on the task branch; only this task's folder on agent-notes
│   │   ├── prepare-commit-msg    # adds the Task: trailer on the task branch
│   │   └── pre-push              # only this task's branch and agent-notes
│   ├── roles/<role>/
│   │   ├── ROLE.md               # identity, method, definition of done, boundaries
│   │   ├── gitconfig             # name, email, key::signing key; includes ../../git/gitconfig
│   │   ├── memory/               # curated knowledge, one file per topic
│   │   └── skills/<name>         # a link to each of the role's skills (../../../skills/<name>)
│   └── skills/
│       ├── LICENSE-mattpocock-skills  # copied from the source repository at that commit
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
| **ProjectClone** | A throwaway, shallow clone of a project's repository that `foundry task create` uses to start a task's branches, made with git and your own access in a folder you give it: lists the remote's branches, checks one out (starting it empty if it doesn't exist), writes and commits files, signing each with SSH and your `user.signingkey`, and pushes branches together |

1. `foundry run PROJECT ROLE TASK` looks the project and role up in `config/foundry.yaml` and names the sandbox `<role>-<project>-<task>`. The first time, it creates the session: the sandbox definition, `sessions/<sandbox>/sbxenv.yaml`, and the empty `sessions/<sandbox>/workspace/` that sbx requires as the primary workspace, though nothing is put in it. A session a stopped launch left without its definition is finished if it holds only an empty `workspace/`, and refused otherwise. Later launches reuse the definition and re-attach, since sbx fixes a sandbox's mounts when it is created. A launch whose role, task or repository differs from the existing definition's is refused, since two of them can slug to one sandbox name, and so is a sandbox whose session variables this foundry would no longer set: one created before a variable was added or renamed, whose kit would use the old names. The launcher never removes a sandbox: to start one over, [recreate it](README.md#recreating-a-sandbox) yourself; its ssh-agent is stopped by the next launch (step 2). The only real mount is `agent-kit/`, read-only. At every launch, the launcher builds `src/agent_runtime/` into that kit's `.build/agent_runtime.pyz`. The kit the sandbox definition records must be this foundry's: a copied foundry launching the original's sandbox is refused, since it would swap the runtime under the original's sandboxes, and so is a moved foundry's, whose kit is gone; both say to recreate the sandbox. The archive is renamed over the old one, so a process that has it open keeps reading the old one whole, and is left alone when nothing changed; a failed build aborts the launch. The session variables, named once in `agent_runtime.contract`, are `AGENT_ROLE`, `AGENT_TASK`, `AGENT_KIT_DIR`, `AGENT_REPO_URL`, `AGENT_PROJECT_DIR`, `AGENT_NOTES_DIR`, and the task's names from `Task`: `AGENT_TASK_BRANCH`, `AGENT_NOTES_BRANCH`, `AGENT_NOTES_ROOT`, `AGENT_TASK_NOTES`, `AGENT_TASK_FILE`, so the kit and its instructions spell none of them out.
2. `foundry.agent_sandbox` first kills the ssh-agents of sandboxes that are stopped or removed, as `foundry prune` does: it compares the agents it started (found by their command line, `ssh-agent -a /tmp/sbx-agents/<sandbox>.sock -s`) with `sbx ls --json`, and kills each whose sandbox is missing or `stopped`; one a launch prepared in the last 10 minutes is spared. An idle agent only holds a private key, and launching its sandbox again starts a new one; sbx lists every sandbox its user has, so another foundry instance's running sandboxes keep their agents. It then starts a private `ssh-agent` for the sandbox holding only `secrets/ssh/<role>`, creates the sandbox from its definition if it doesn't exist (`sbx env create`), allows `github.com:22`, seeds GitHub's host keys, and checks from inside that the sandbox sees exactly that one key. If `secrets/github/<role>.token` exists, sbx is told to read the token from it on the host (`sbx secret set --command`), so the launcher never handles the token itself; otherwise the `github` secret is cleared.
3. It runs the runtime's `session-init` inside the sandbox (`sbx env exec`, as `/usr/bin/python3 -IS agent-kit/.build/agent_runtime.pyz session-init`), which first runs `session-setup` as the agent user: it stops at once if the role's folder lacks `ROLE.md` or `gitconfig`, as `foundry` refuses on the host, then clones `$AGENT_REPO_URL` into `$AGENT_PROJECT_DIR`, checks out `$AGENT_TASK_BRANCH`, adds the `agent-notes` worktree, points `core.hooksPath` at the kit, includes the role's `gitconfig`, writes the agent's `~/.claude/CLAUDE.md` importing `AGENTS.md`, the role's `ROLE.md` and the task's `TASK.md` so the agent starts briefed, links the role's `skills/` folder as `~/.claude/skills` (see [Skills](docs/skills.md)). On the first launch, `session-init` then runs `harden` as root, through sudo, given only `AGENT_KIT_DIR`: it installs Claude's managed settings, links `/etc/claude-code/agent_runtime.pyz`, which their hooks and the git hooks run, to the kit's runtime, and removes the agent's ways to root: sudo, `su` (root's password is locked) and Docker, whose daemon mounts the sandbox's own filesystem. sbx gives agent processes the `docker` group whatever `/etc/group` says, so the Docker socket is made root-only instead (`/etc/docker/daemon.json` sets its group to `root`, and the current socket is changed too). On every launch, `session-init` then runs `check-hardening` as the agent, with the groups sbx gives it: it checks that the agent can't run sudo, can't `su` to root, can't write to the Docker socket, that the managed settings are root-owned, read-only and the same as `agent-kit/claude/managed-settings.json`, that the hooks' link points to the kit's runtime, in a folder root owns, that it can't write anywhere in the agent kit, which proves the mount is read-only, that every folder from `/` down to the kit belongs to root and lets it rename nothing on the way, since another kit put at the path would be what the hooks' link reaches, and that `/usr/bin/python3` resolves to a root-owned file it can't write, since every hook runs it. A sandbox that fails any check doesn't start the agent, naming every check it failed; one hardened by an older kit needs [recreating](README.md#recreating-a-sandbox). The launch aborts if any step fails.
4. `sbx env run` attaches the agent, with permission prompts off (see [What protects what](docs/security-model.md)). It works per `AGENTS.md` and its `ROLE.md`, committing code to `task/<task>` and notes to `agent-notes`, pushing both.
5. The launcher replaces itself with `sbx`, so it never learns how the session ended, or even whether the agent started. Harvest (not yet built) will record the outcome. It reads `LEARNINGS.md` from `agent-notes` and files cross-project lessons into the role's `memory/`.

Each command has a composition root that builds the real dependencies (`run.main`, `task.create_main`, `repo.check_main`, `skills.update_main`, `prune.main`) and a function that takes them as parameters (`run.prepare_launch`, `task.create`, `repo_policy.check_project` and `fix_project`, `skills.update`; `prune.main` reports what `agent_sandbox.prune` removed), which is what the tests call, with fakes for GitHub, the sandbox and the host's processes (`FakeGitHub` in `tests/test_repo_policy.py`, its only user, and fixtures in `tests/agent_sandbox/conftest.py`) and no patching.

Preconditions the launcher does not create: the task, which `foundry task create PROJECT TASK` creates in the project's repository, with git and your own access to it: the branch `task/<task>` from the default branch, and `.agent/<task>/` on `agent-notes`, a copy of `config/task-template/` (`TASK.md`, `PROGRESS.md`, `LEARNINGS.md`; a template without a `TASK.md` is refused). Task ids are lowercased, by `foundry task create` and `foundry run` alike: `WCF-0042` is task `wcf-0042`. Then write the task in its `TASK.md` yourself, or run the planner, which drafts it with you and writes it once you approve. The first task creates `agent-notes` as an orphan branch, sharing no history with the code. It refuses a task that already exists. Both branches are pushed together (`git push --atomic`), so a failure leaves neither.

## The launcher

```
src/foundry/
├── cli.py              # `foundry` command; one subcommand per module in commands/
├── commands/run.py     # foundry run
├── commands/task.py    # foundry task create
├── commands/repo.py    # foundry repo check [--fix]
├── commands/prune.py   # foundry prune
├── commands/skills.py  # foundry skills update
├── runtime_build.py    # builds src/agent_runtime/ into a kit's .build/agent_runtime.pyz, atomically
├── repo_policy.py      # the repo policy: loads it, lists a repository's deviations, applies its rulesets
├── skills.py           # the kit's copied skills: read their source, merge upstream's changes in (plan, then apply)
├── task.py             # Task: a task's id, branch and notes folder; creating one, its notes from the template (agent-notes, an orphan, is created by the first)
├── github.py           # the GitHub interface foundry needs, and GhCli: it through `gh api`, signed in as you
├── project_clone.py    # ProjectClone: a throwaway, shallow clone of a project's repository, through agent_runtime.git: check out, write, commit, push
├── paths.py            # the only module that knows the instance layout, functions taking root; what is inside the agent kit is agent_runtime.agent_kit's
├── config.py           # loads and validates config/foundry.yaml; Role: a role's SSH key and optional token
├── session.py          # open_or_create: names the sandbox, creates its session once, refuses a collision; SessionVariables
├── yaml_io.py          # YAML load with user-facing errors
├── errors.py
└── agent_sandbox/      # runs one sandbox safely; imports nothing from foundry (a test checks)
    ├── launcher.py     # LaunchRequest, launch() and prepare(): the sequence in steps 2–3 above, against the Sandbox port; start() runs it up to attaching the agent and returns a PreparedSandbox, for launch and the sbx smoke tests
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
├── contract.py           # the AGENT_* names, which foundry.session also uses, and reading them back; the sandbox's user
├── agent_kit.py          # where everything sits in the agent kit, what a role's folder must hold, and how its runtime is called; foundry imports it too
├── session_init.py       # what the launcher runs: setup, hardening on the first launch, then the check on every launch. Owns the handoff to root: the sudo probe, the root command, and the `harden` and `check-hardening` entries
├── session_setup.py      # the agent user's part: refuses a role folder without ROLE.md or gitconfig, then clones the project, sets up checkouts, hooks, identity, instructions
├── hardening.py             # what each mode does, on a Machine: as root, installs Claude's managed settings, removes sudo and su, makes the Docker socket root-only; as the agent, checks it all
├── claude_hooks.py       # guard_bash (PreToolUse), session_check (Stop)
├── git_hooks.py          # pre_commit, prepare_commit_msg, pre_push, which agent-kit/hooks/ run through git-hook, and their refusals
├── atomic_files.py       # atomic_write and atomic_symlink: a file or link replaced in one step; foundry imports it too
└── git.py                # Git: the one way both packages run git (output, output_bytes, result, succeeds), and GitError; foundry imports it too
```

`foundry` imports four of these modules, `contract`, `agent_kit`, `files` and `git`, and never the reverse; `tests/test_runtime_boundary.py` checks it. A git failure on the host is a `GitError`, which the CLI reports as it does a `FoundryError`.

| Command (`/usr/bin/python3 -IS agent_runtime.pyz …`) | Run by |
|---|---|
| `session-init` | the launcher, as the agent, before the agent starts |
| `session-setup` | `session-init`; never needs root |
| `harden` | `session-init`, as root through sudo on the first launch, given `AGENT_KIT_DIR` alone: `session_init.harden` |
| `check-hardening` | `session-init`, as the agent on every launch: `session_init.check_hardening` |
| `claude-hook guard-bash`, `claude-hook session-check` | Claude Code, from managed settings |
| `git-hook pre-commit`, `git-hook prepare-commit-msg`, `git-hook pre-push` | git, from the stubs in `agent-kit/hooks/` |

It targets the repository's Python floor, 3.11, like `foundry`, and the sandbox template ships a newer one, so the tests on CI's Python versions cover it. `__main__` still checks the version before importing anything else, so a template that someday ships an older `python3` fails at `session-init` with what it needs.
