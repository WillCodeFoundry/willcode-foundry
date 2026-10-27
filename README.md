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

## Recreating a sandbox

sbx fixes a sandbox's definition and mounts when it creates it, so some sandboxes can't be launched again and must be recreated:

- **one created before the agent runtime,** when the kit's code was bash scripts: its managed settings run hooks that no longer exist, and `check-hardening` refuses it. Recreate every sandbox after updating to this version;
- **one hardened while the Claude hooks' command was `hook`,** before it became `claude-hook`: its installed managed settings differ from the kit's, and `check-hardening` refuses it;
- **one created with other session variables,** before one was added or renamed: the launch is refused, naming the variables that differ;
- **one whose workspace was under `/tmp`,** from before the workspace moved into the session: once the OS clears it, launching fails with `workspace '…' is not a directory`.

To recreate one: `sbx env rm --force sessions/<sandbox>`, delete `sessions/<sandbox>/`, and launch again.

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
