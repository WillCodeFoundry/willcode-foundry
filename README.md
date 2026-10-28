# willcode-foundry

The foundry runs coding agents on your projects. Each agent works in its own Docker Sandbox, with one role and one task, and hands its work back by pushing branches to the project's GitHub repository. This repository holds the configuration, the roles and the code that launches them; it holds no project code.

## Requirements

- **sbx**, the Docker Sandboxes CLI, signed in, with SSH agent forwarding on and not pinned to a socket:

  ```console
  $ sbx settings set ssh.agentForwardingEnabled true
  $ sbx settings unset ssh.agentSocketPath
  $ sbx daemon restart
  ```

- **uv**, to run foundry.
- **git**, with an SSH signing key named in your global config, to create tasks. See [Where agent output lives](#where-agent-output-lives).
- **gh**, signed in with admin rights on the projects, for `foundry repo check`.

## Set up

1. List your projects and roles in `config/foundry.yaml`. Each role needs its dir in `agent-kit/roles/<role>/`, holding its `ROLE.md` and its `gitconfig`, which sets the role's GitHub user name, email and SSH signing key. Add each signing key to `agent-kit/git/allowed_signers`.
2. Put each role's SSH key in `secrets/ssh/<role>`. If a role should use `gh`, put its GitHub token in `secrets/github/<role>.token`. The dev opens pull requests, so it needs one that can.
3. Make each project's repository match the repo policy: see [config/repo-policy/](config/repo-policy/README.md).

## Use

```console
$ uv sync
$ uv run foundry task create tkt-store wcf-0042   # create the task: its branch, its notes and its task state
$ uv run foundry task run tkt-store wcf-0042      # start whoever's turn it is on the task, or re-attach to it
$ uv run foundry task list                        # every task: its state, whose turn it is, its hand-off note
```

Task ids are lowercased: `WCF-0042` is task `wcf-0042`. A new `feature` task starts with the planner, which drafts its `TASK.md` with you and writes it once you approve. `uv tool install --editable .` puts `foundry` on your PATH.

| Command | What it does |
|---|---|
| `foundry task create PROJECT TASK [--lifecycle NAME]` | Creates a task: its branch, and its notes and task state on `agent-notes`. |
| `foundry task run PROJECT TASK` | Starts the sandbox of the role whose turn it is, or re-attaches to it. |
| `foundry task list` | Lists every task of every project: its state, whose turn it is, whether that turn's sandbox runs, and its hand-off note. |
| `foundry task move PROJECT TASK STATE --note NOTE` | Moves a task by hand to any state of its lifecycle. |
| `foundry repo check [--fix] [PROJECT ...]` | Compares projects' repositories with the [repo policy](config/repo-policy/README.md). |
| `foundry prune` | Stops the ssh-agents of sandboxes that are stopped or removed, sparing any started in the last 10 minutes. `foundry task run` does this too. |
| `foundry skills update [COMMIT]` | Merges upstream's changes into the agent kit's copied [skills](docs/skills.md). |

foundry approves each sandbox's plan for you (`--auto-approve`). Each plan mounts only `agent-kit/`, read-only, and an empty dir.

## Task states

A task passes from role to role along its lifecycle. Its task state, `.agent/<task>/STATE.json` on `agent-notes`, says which state it is in, whose turn that makes it, and the hand-off note the last turn left. The lifecycles are in `src/agent_runtime/task/lifecycles.py`; [ADR 0011](docs/adr/0011-task-states.md) says why they are code.

| State | Turn | Ends with |
|---|---|---|
| `plan` | planner | `submit` → `implement`, once you approve its `TASK.md` |
| `implement` | dev | `submit` → `review` |
| `review` | reviewer | `approve` → `deliver`, or `reject` → `implement` |
| `deliver` | dev | `submit` → `done`, once the pull request is open |
| `blocked` | you | your `foundry task move` |
| `done` | no one | |

That is `feature`, the default. `bugfix` is the same without `plan`: write its `TASK.md` yourself, before its first run. Every role can also `block`, handing the task to you with a question as its note.

Agents end their turns with `agent-kit/bin/task`. A push that changes `STATE.json` must make a legal transition for that role, or `pre-push` refuses it. `foundry task run` launches only the role whose turn it is.

Move a task by hand with `foundry task move PROJECT TASK STATE --note "…"`. It commits the task state as you, signed, and pushes `agent-notes`. The usual moves:

- **After an agent's question:** answer it, in `TASK.md` or the note, and move the task back to the state it came from. `foundry task run` prints that state.
- **After the review limit:** from round 3 on, the reviewer blocks instead of rejecting. Move the task on to `deliver`, back to `implement` for one more round, or to `plan` to rescope it.
- **After it is done:** if the pull request needs more work, move it back to `implement`.

In `foundry task list`, `SANDBOX` is `running` while the sandbox of the role whose turn it is runs. A `—` on a role's turn means no one is working on it: the agent stopped without ending its turn, or was never launched. `foundry task run` starts it again.

## Where agent output lives

Agents write nothing to this repository. Their work goes to the project's repository, on two branches:

| Branch | Holds | Written by |
|---|---|---|
| `task/<task>` | Code and project documentation | dev, qa |
| `agent-notes` | `.agent/<task>/`: `TASK.md`, `PROGRESS.md`, `LEARNINGS.md`, `REVIEW.md`, `STATE.json` | every role, each only in its own task's dir; `STATE.json` only through `agent-kit/bin/task` and `foundry task move` |

`TASK.md` is yours. Nothing stops another role from changing it, so the reviewer checks its history and reports any change. Sign your own commits on `agent-notes` with SSH, since the reviewer reports unsigned changes to `TASK.md`. `foundry task create` always signs the commit that creates the task, with your key, and refuses to create the task if it can't:

```console
$ git config --global user.signingkey ~/.ssh/id_ed25519.pub   # your line in allowed_signers; its private half in your ssh-agent
```

In your own clone of the project, turn on signing for that clone only:

```console
$ git config gpg.format ssh
$ git config commit.gpgsign true
```

## Recreating a sandbox

foundry never rewrites, re-hardens or removes a sandbox ([ADR 0004](docs/adr/0004-sandboxes-are-immutable.md)). One it would now create or harden differently has to be recreated:

```console
$ sbx env rm --force sessions/<sandbox>
$ rm -r sessions/<sandbox>/
$ uv run foundry task run PROJECT TASK
```

This applies to:

- a sandbox created with other session variables, or from another foundry's kit (one that was copied or moved): the launch is refused, saying what differs;
- a sandbox hardened before a change to the managed settings or to hardening: `check-hardening` refuses it.

Push the agent's work first, since removing the sandbox deletes anything left in it.

## More

| Read | For |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the foundry is put together, and the design rules its code follows. |
| [GLOSSARY.md](GLOSSARY.md) | The words the code and docs use. |
| [docs/adr/](docs/adr/README.md) | Why it works this way: one record per decision. |
| [docs/security-model.md](docs/security-model.md) | What protects what, and what is only a guardrail. |
| [docs/skills.md](docs/skills.md) | The agents' skills, and updating them from upstream. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Developing the foundry: the test tiers and CI. |
