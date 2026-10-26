# willcode-foundry

The foundry runs coding agents in sandboxes, one role per task, and hardens each sandbox so its agent can't become root. The README's "How a session runs" defines the terms of a launch; this file holds the ones it doesn't.

## Language

**Machine**:
The place hardening acts on and checks: the sandbox's system files and sockets, the commands that reach root, and what the agent can do to them. `SANDBOX` is the real one; tests build temporary ones.
_Avoid_: host, environment, system
