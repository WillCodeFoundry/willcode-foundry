# A role's model is given at each launch

A role's model is set in `config/foundry.yaml`, and `foundry run` passes it to Claude Code as `--model` when it attaches. It isn't part of the sandbox, so changing it takes effect at the next launch, without recreating anything ([ADR 0004](0004-sandboxes-are-immutable.md)). It is a default, not a control: you, or the agent, can still change it in a run with `/model`.

## Considered options

- **A session variable, such as `ANTHROPIC_MODEL`.** Variables are fixed when the sandbox is created, so changing a role's model would mean recreating every sandbox it has.
- **`model` in the managed settings.** The agent couldn't override it, but the managed settings are one file for every role. Changing them also fails `check-hardening` in every existing sandbox.
