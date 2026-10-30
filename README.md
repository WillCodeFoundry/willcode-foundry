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
2. Put each role's SSH key in `secrets/ssh/<role>`. If a role should use `gh`, put its GitHub token in `secrets/github/<role>.token`. The dev opens pull requests and reads their CI, so its token needs pull requests read and write, and Actions read.
3. Make each project's repository match the repo policy: see [config/repo-policy/](config/repo-policy/README.md).

## Use

```console
$ uv sync
$ uv run foundry task create tkt-store wcf-0042   # create the task: its branch, and its notes from config/task-template/
$ uv run foundry run tkt-store wcf-0042           # start the role whose turn it is
```

Task ids are lowercased: `WCF-0042` is task `wcf-0042`. Write the task in its `TASK.md` on the `agent-notes` branch, or start the planner, which drafts it with you and writes it once you approve. `uv tool install --editable .` puts `foundry` on your PATH.

A task passes from role to role: planner, dev, reviewer, then back to the dev for the pull request. When a task changes how the code is structured, the planner hands it to the architect first, who agrees a `DESIGN.md` with you. Its `TURN` file on `agent-notes` names whose turn it is, or `human` when the task waits for you, with the question in its `PROGRESS.md`. To hand it on yourself, edit `TURN`, or name the role to `foundry run`. When you write `TASK.md` yourself, write `dev` in `TURN` too, or the planner starts.

| Command | What it does |
|---|---|
| `foundry run PROJECT [ROLE] TASK` | Starts the sandbox for a role on a task, or re-attaches to it. Without ROLE, the role whose turn it is. |
| `foundry task create PROJECT TASK` | Creates a task: its branch, and its notes in `.agent/tasks/open/<task>/` on `agent-notes`. |
| `foundry task close PROJECT TASK` | Moves the task's notes to `.agent/tasks/closed/<task>/`. Its branch and sandboxes stay. |
| `foundry task reopen PROJECT TASK` | Moves the task's notes back to `.agent/tasks/open/<task>/`. |
| `foundry repo check [--fix] [PROJECT ...]` | Compares projects' repositories with the [repo policy](config/repo-policy/README.md). |
| `foundry prune` | Stops the ssh-agents of sandboxes that are stopped or removed, sparing any started in the last 10 minutes. `foundry run` does this too. |
| `foundry skills update [COMMIT]` | Merges upstream's changes into the agent kit's copied [skills](docs/skills.md). |

foundry approves each sandbox's plan for you (`--auto-approve`). Each plan mounts only `agent-kit/`, read-only, and an empty dir.

## Where agent output lives

Agents write nothing to this repository. Their work goes to the project's repository, on two branches:

| Branch | Holds | Written by |
|---|---|---|
| `task/<task>` | Code and project documentation | dev, qa |
| `agent-notes` | `.agent/tasks/open/<task>/`, or `closed/` once closed: `TASK.md`, `DESIGN.md`, `PROGRESS.md`, `LEARNINGS.md`, `REVIEW.md` | every role, each only in its own task's dir |

`TASK.md` is yours. Nothing stops another role from changing it, so the reviewer checks its history and reports any change. Sign your own commits on `agent-notes` with SSH, since the reviewer reports unsigned changes to `TASK.md`. `foundry task create`, `close` and `reopen` always sign their commit with your key, and refuse if they can't:

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
$ uv run foundry run PROJECT ROLE TASK
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
