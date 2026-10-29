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
One task's dir on the notes branch, `.agent/<id>/`: its `TASK.md`, `PROGRESS.md`, `LEARNINGS.md`, `REVIEW.md` and `STATE.json`. Each role writes only in its own task's dir.
_Avoid_: notes folder, notes dir (that is the notes checkout)

**Code checkout** and **notes checkout**:
The two working copies of a project inside a sandbox: one on the task branch, one on the notes branch.

**Task template**:
`config/task-template/`, the files every new task's notes dir starts from.

### Task states

**Lifecycle**:
The state machine one kind of task follows, such as `feature` or `bugfix`. Defined in `src/agent_runtime/task/lifecycles.py`.
_Avoid_: workflow, pipeline

**State**:
One named step of a lifecycle, such as `review`, with its role, its goal and its events. A terminal state, such as `blocked` or `done`, has none of them.
_Avoid_: stage, status

**Task state**:
A task's `STATE.json`: its lifecycle, the state it is in, and the hand-off note. Its history is the file's history on the notes branch. "The task is in `review`."
_Avoid_: ticket

**Terminal state**:
A state no event leaves, and which belongs to no role. Only a human, moving the task by hand, takes it elsewhere. `blocked`, where a question waits for a human, and `done` are terminal.
_Avoid_: final state, the human's state

**Turn**:
The time a task is in a state assigned to a role. Only that role is launched on the task. A turn can span several agent runs.
_Avoid_: session (that is the foundry's record of a sandbox)

**Event**:
What an agent sends with the task command to end its turn. The lifecycle names each state's events, and which state each leads to. The turn ends when the task state it writes is pushed.
_Avoid_: action, command

**Transition**:
An event applied to a task state, or a move by hand with `foundry task move`.

**Hand-off note**:
The note a transition leaves for whoever is next, who reads it first. In `blocked`, it is the question for the human.

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
One `foundry task run`: starting a sandbox, or re-attaching to it. The **first launch** creates and hardens it; a **relaunch** sets it up again and checks it, without hardening.

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
`prepare-commit-msg` and `pre-push`, which git runs in both checkouts.

**Claude hooks**:
`guard-bash`, which Claude Code runs before each shell command, and `session-check`, which it runs each time the agent stops.

**Refusal**:
What a hook, a hardening mode or the task command says when it stops something: what is wrong, and which rule it breaks.

### Testing

**Tier**:
A level of tests. The **host** tier runs everywhere; the **docker** tier runs the runtime in the template image; the **sbx** tier launches a real sandbox, by hand.

## Relationships

- A **project** has many **tasks**; a **task** has one **task branch** and one **task notes dir** on the project's **notes branch**.
- A **task** has one **task state**, which names one **lifecycle** and one of its **states**.
- A **turn** spans one or more **agent runs** of its state's **role**.
- A **sandbox** runs one **role** on one **task** of one **project**, and has one **session**.
- A **sandbox** sees one **agent kit**, read-only; the **runtime** in it does the **hardening** and runs the **hooks**.
- A **sandbox** has many **launches** and **agent runs** over its life; its **session variables** stay the same for all of them.

## Flagged ambiguities

- "session" meant both the foundry's record of a sandbox and one run of Claude Code. Resolved: **session** is the record, **agent run** is the run.
- "notes dir" meant both a task's dir on the notes branch and the notes checkout. Resolved: **task notes dir** and **notes checkout**.
- "launcher" meant both the whole foundry and `agent_sandbox/launcher.py`. Resolved: **foundry** for the whole.
- "template" meant both the task template and the template image. Resolved: always say which.
- "state" could mean a lifecycle's step or the record of which step a task is in. Resolved: **state** is the step, **task state** is the record. "Status" is for neither: it is a sandbox's (`running`).
