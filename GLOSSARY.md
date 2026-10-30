# willcode-foundry

The foundry runs coding agents on a set of projects, each agent in its own sandbox with one role and one task. These are the words its code, docs and messages use.

## Language

### The foundry and its projects

**Foundry**:
This repository and the `foundry` command it provides: the configuration, agent kit, secrets and sessions for a set of agents working on a set of projects.
_Avoid_: launcher (for the whole tool; `agent_sandbox/launcher.py` is one part of it), instance

**Project**:
A code repository agents work on, listed in `config/foundry.yaml`.
_Avoid_: repo, repository (except for the GitHub repository behind a project, or the foundry's own)

**Repo policy**:
What every project's GitHub repository must match: its rulesets, its CODEOWNERS and the `ci-gate` job of its CI.

**Deviation**:
One way a project's repository differs from the repo policy, shown as a diff. A repository with none **conforms**.

**ci-gate**:
The last job of a project's CI, which passes only if every other job did: the one check the rulesets require.

### Roles and tasks

**Role**:
Who an agent is (planner, dev, qa, reviewer or architect): its instructions, its git identity, its SSH key and, optionally, its GitHub token.

**Task**:
A unit of work on one project: a task branch, plus a task notes dir on the notes branch holding the task's `TASK.md`.

**Task id**:
A task's name, lowercase, such as `wcf-0042`.

**Task branch**:
The branch a task's code is committed to, `task/<id>`.

**Notes branch**:
The one branch in each project, `agent-notes`, that holds every task's notes. It shares no history with the code.
_Avoid_: notes worktree (that is the notes checkout)

**Notes root**:
The dir on the notes branch, `.agent/`, under which every task's notes sit. Nothing under it belongs on a task branch.

**Task notes dir**:
One task's dir on the notes branch, `.agent/<id>/`: its `TASK.md`, `DESIGN.md` when the task had an architect turn, `PROGRESS.md`, `LEARNINGS.md`, `REVIEW.md` and `TURN`. Each role writes only in its own task's dir.
_Avoid_: notes folder, notes dir (that is the notes checkout)

**Turn**:
Which role works on a task next, or `human` when it waits for you. The task's `TURN` file holds it, and each role writes the next one when its turn ends.
_Avoid_: task state, lifecycle

**Code checkout** and **notes checkout**:
The two working copies of a project inside a sandbox: one on the task branch, one on the notes branch.

**Task template**:
`config/task-template/`, the files every new task's notes dir starts from.

### Sandboxes and sessions

**Sandbox**:
The Docker Sandbox one role works on one task in. It is named `<role>-<project>-<task>`.

**Sandbox definition**:
What sbx creates a sandbox from, written once when the sandbox is first launched.

**Session**:
The foundry's record of one sandbox: its dir in `sessions/`, holding the sandbox definition.
_Avoid_: session (for one run of Claude Code; that is an agent run)

**Session variables**:
The `AGENT_*` environment variables a sandbox is created with, which tell the agent kit everything about its role, project and task. They never change for the life of the sandbox.

**Launch**:
One `foundry run`: starting a sandbox, or re-attaching to it. The **first launch** creates and hardens it; a **relaunch** sets it up again and checks it, without hardening.

**Opening prompt**:
The fixed first message foundry sends when it attaches the agent.

**Agent run**:
One run of Claude Code inside a sandbox, from start until the agent stops.
_Avoid_: session

**Template image**:
The image sbx creates Claude Code sandboxes from.
_Avoid_: template (alone; that also means the task template)

### What an agent is given

**Agent kit**:
Everything an agent is given, mounted read-only into every sandbox: shared instructions, roles, skills, Claude Code's managed settings, the git hook stubs and the built runtime.
_Avoid_: kit dir (for anything but its path)

**Runtime**:
The Python program that runs inside a sandbox around the agent: setup, hardening and the hooks. It is built into the agent kit at every launch.
_Avoid_: pyz, zipapp (for the program rather than its file)

**Managed settings**:
Claude Code's policy, installed where only root can change it: which hooks run, and what the agent may do without asking.

**Skill**:
A procedure Claude Code loads and follows. A **copied skill** comes from an upstream repository and records which commit it is up to date with; the foundry's own skills have no upstream. A role's skills are the ones linked from its role dir.

**Memory**:
A role's curated knowledge across projects. Not yet filled by anything.

**Harvest**:
A planned step, not yet built, that would file the lessons in a task's `LEARNINGS.md` into its role's memory.

### Hardening

**Hardening**:
Making a sandbox such that the agent can't become root, change the managed settings, or change the code they run; and checking that this holds.

**Root mode**:
Hardening as root, on the first launch, while sudo still works. Its command is `harden`.

**Agent mode**:
The check that hardening holds, run as the agent on every launch. Its command is `check-hardening`.
_Avoid_: verify

**Boundary**:
A control that holds whatever the agent does: the sandbox itself, the read-only agent kit, the managed settings, the project's rulesets.

**Guardrail**:
A control that stops mistakes, not an agent set on getting past it: the git hooks and the Claude hooks.
_Avoid_: boundary, security (for a guardrail)

**Git hooks**:
`pre-commit`, `prepare-commit-msg` and `pre-push`, which git runs in both checkouts.

**Claude hooks**:
`guard-bash`, which Claude Code runs before each shell command, and `session-check`, which it runs at the end of each of the agent's turns.

**Refusal**:
What a hook or a hardening mode says when it stops something: what was wrong, and what to do instead.

### Testing

**Tier**:
A level of tests. The **host** tier runs everywhere; the **docker** tier runs the runtime in the template image; the **sbx** tier launches a real sandbox, by hand.

## Relationships

- A **project** has many **tasks**; a **task** has one **task branch** and one **task notes dir** on the project's **notes branch**.
- A **sandbox** runs one **role** on one **task** of one **project**, and has one **session**.
- A **sandbox** sees one **agent kit**, read-only; the **runtime** in it does the **hardening** and runs the **hooks**.
- A **sandbox** has many **launches** and **agent runs** over its life; its **session variables** stay the same for all of them.

## Flagged ambiguities

- "session" meant both the foundry's record of a sandbox and one run of Claude Code. Resolved: **session** is the record, **agent run** is the run.
- "notes dir" meant both a task's dir on the notes branch and the notes checkout. Resolved: **task notes dir** and **notes checkout**.
- "launcher" meant both the whole foundry and `agent_sandbox/launcher.py`. Resolved: **foundry** for the whole.
- "template" meant both the task template and the template image. Resolved: always say which.
