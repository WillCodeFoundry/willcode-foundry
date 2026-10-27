# Sandbox code is one stdlib-only Python runtime, run from the read-only kit through paths the agent can't redirect

The code that sets up, hardens and guards a sandbox is `src/agent_runtime/`, built into `agent-kit/.build/agent_runtime.pyz` and run from the kit's read-only mount, never copied in: a writable copy would let the agent change what a hook does. It uses only the standard library, so it runs on the sandbox template's own `/usr/bin/python3` with nothing installed. Every call is `/usr/bin/python3 -IS`, so no `PYTHON*` variable or `.pth` file runs first. Hooks reach it only through `/etc/claude-code/agent_runtime.pyz`, a link hardening makes in a folder only root can write, because the agent can set the environment of Claude Code and of its own git.

## Considered options

- **Bash scripts in the kit.** Hard to test outside a sandbox, and covered only by a linter.
- **Finding the runtime through `$AGENT_KIT_DIR`, or the hook stubs' own path.** A settings file the agent writes can change the first, and the second needed its own path logic in every stub.
- **`env python3`.** It follows the agent's `PATH`.

Source: #20.
