# willcode-foundry

This repository is one instance of a willcode foundry: the configuration, role definitions and memory for a set of coding agents working on a group of projects. It holds no project code. Agents work on in-sandbox clones of each project and hand work back by pushing branches.

## Layout

```
.
├── README.md
├── .gitignore
├── config/
│   └── foundry.yaml              # instance-wide settings
├── agents/                       # everything an agent is given (read-only mount)
│   ├── AGENTS.md                 # instructions shared by every role
│   ├── bin/
│   │   ├── session-init.sh       # prepares a sandbox before the agent starts
│   │   └── hook-rules.sh         # lists every rule the hooks enforce
│   ├── hooks/
│   │   ├── pre-commit            # dispatches by branch to lib/
│   │   ├── pre-push
│   │   └── lib/
│   │       ├── common.sh
│   │       ├── check-code-commit.sh
│   │       ├── check-notes-commit.sh
│   │       └── check-push.sh
│   ├── roles/
│   │   ├── planner/
│   │   │   ├── ROLE.md
│   │   │   ├── setup.sh          # role-specific setup, optional
│   │   │   ├── checklist.md
│   │   │   ├── templates/TASK.md
│   │   │   ├── examples/
│   │   │   └── memory/
│   │   ├── dev/
│   │   │   ├── ROLE.md
│   │   │   └── memory/
│   │   │       ├── testing.md    # curated knowledge, one file per topic
│   │   │       └── database.md
│   │   ├── qa/
│   │   │   ├── ROLE.md
│   │   │   └── memory/
│   │   └── reviewer/
│   │       ├── ROLE.md
│   │       └── memory/
│   └── skills/
│       ├── git-conventions/
│       │   └── SKILL.md
│       └── run-tests/
│           └── SKILL.md
├── secrets/                      # untracked except .gitkeep files
│   ├── ssh/
│   │   ├── dev                   # one keypair per role, named after the role
│   │   ├── dev.pub
│   │   └── ...
│   └── env/
│       ├── dev.env               # API keys for the dev role's sandbox
│       └── ...
└── sessions/                     # untracked, written only by the foundry
    ├── dev-20261009-1412/
    │   ├── session.yaml          # role, task, timings, outcome
    │   ├── sbxenv.yaml           # the sandbox environment file used
    │   └── log/
    │       └── sandbox.log       # captured sandbox output
    └── archive/
```

| Folder | Written by | Tracked |
|---|---|---|
| `config/` | You | Yes |
| `agents/` | You, plus the harvest step for `memory/` | Yes |
| `secrets/` | You | No |
| `sessions/` | The foundry | No |

## `config/`

- `foundry.yaml`: instance name, pinned foundry tool version, projects (repo URL, default branch), and per-role settings the foundry enforces: model, sandbox profile, SSH key, limits. These live here so `ROLE.md` stays plain markdown.

## `agents/`

Everything a sandbox is given. Mounted read-only in full, so an agent can read its own definition, memory and hooks but never change them. Inside the sandbox its path is in `$AGENT_KIT_DIR`.

### `AGENTS.md`

Standing instructions every role receives: environment, task notes, workflow, git rules, safety. Short and imperative. Each role's `ROLE.md` adds to it and wins where they disagree; the project's own `AGENTS.md` wins for anything about the code.

### `bin/`

- `setup.sh`: run by the foundry before the agent starts. Sets git identity from the role, points `core.hooksPath` at `agents/hooks/`, switches to `task/$AGENT_TASK`, adds the notes worktree on `agent-notes`, checks `TASK.md` exists, then runs the role's `setup.sh` if there is one. It creates nothing: the task branch and skeleton notes must already exist, and anything missing is an error.
- `rules.sh`: prints the rules the hooks enforce, so you or an agent can see them without triggering one.

### `hooks/`

Git hooks for both checkouts, reached through `core.hooksPath`. Because the mount is read-only, agents cannot alter or bypass them. `pre-commit` and `pre-push` are thin dispatchers; the rules live in `lib/` and each refusal message says what was wrong and what to do instead. The rules are the source of truth; `AGENTS.md` describes the intent and tells agents to read the message.

| Script | Enforces |
|---|---|
| `check-code-commit.sh` | No task notes or credential files on the task branch |
| `check-notes-commit.sh` | Only `.agent/<task>/` changes on `agent-notes`; `TASK.md` never modified |
| `check-push.sh` | Only `task/<task>` and `agent-notes` pushed; no deletes; fast-forward only |

### `roles/`

One folder per role, holding everything specific to it. `ROLE.md` is plain markdown: identity, method, definition of done, boundaries. `memory/` is curated knowledge as topic files, written only by the harvest step and reviewed like code. A role may add `setup.sh` for extra preparation and any supporting files it needs, as the planner does with its template, checklist and examples.

The planner is the one interactive role: it runs with the human present to improve an existing `TASK.md`, writing its proposal to `TASK.proposed.md` for the human to apply.

### `skills/`

Reusable procedures shared across roles, one folder each with a `SKILL.md`. A role reads a skill when it is about to do the work the skill covers, not at session start.

## `secrets/`

Credentials handed to sandboxes. Nothing here is tracked except the `.gitkeep` files that preserve the layout.

Each role's SSH key carries that role's GitHub permissions, so a reviewer key should not be able to push. `config/foundry.yaml` maps each role to its key and env file.

## `sessions/`

One folder per agent session, written only by the foundry on the host. Sandboxes never mount this folder; everything an agent produces leaves the sandbox through a git push.

- Session folders are named `<role>-<YYYYMMDD>-<HHMM>`.
- `session.yaml` is written at launch (role, task, previous session) and completed at exit (status, whether a push happened, final commit, turns, cost).
- `sbxenv.yaml` is the sandbox environment file the foundry generated for this session: template, kits, mounts and the `AGENT_*` variables. Kept outside any mount so the agent cannot alter it.
- `log/` holds what the foundry captures from outside the sandbox.
- After harvest, the folder moves to `archive/`.

## Where agent output lives

Agents write nothing to this repository. Their work goes to the project repository on two branches:

| Branch | Holds | Written by |
|---|---|---|
| `task/<task-id>` | Code and project documentation | dev, qa |
| `agent-notes` | `.agent/<task-id>/TASK.md`, `PROGRESS.md`, `LEARNINGS.md`, `TASK.proposed.md` | all roles, each only in its own task folder |

`TASK.md` is created by the foundry when the task is created and owned by the human. The harvest step reads `LEARNINGS.md` from `agent-notes` and files cross-project lessons into the role's `memory/`.

## How a session runs

1. The foundry creates `sessions/<role>-<timestamp>/` and writes `session.yaml` and `sbxenv.yaml`. The task branch and skeleton notes already exist from task creation.
2. It starts the sandbox from `sbxenv.yaml`: the project cloned inside, `agents/` mounted read-only, and `AGENT_TASK`, `AGENT_ROLE`, `AGENT_PROJECT_DIR`, `AGENT_NOTES_DIR`, `AGENT_KIT_DIR` set.
3. `agents/bin/setup.sh` runs and must succeed before the agent gets control.
4. The agent works, following `AGENTS.md` and its `ROLE.md`, committing code to the task branch and notes to `agent-notes`, pushing both regularly.
5. The foundry records the outcome in `session.yaml`, harvests learnings from `agent-notes`, and archives the session.
