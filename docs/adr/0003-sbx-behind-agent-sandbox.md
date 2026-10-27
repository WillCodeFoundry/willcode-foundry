# sbx is reached only through `agent_sandbox`

Docker marks `sbx env` as experimental. So everything that talks to sbx lives in `foundry.agent_sandbox`, which imports nothing from the rest of foundry. Within it, only `definition.py` knows the sandbox definition's format and only `sandbox.py` knows sbx's command lines, so a change in sbx is one edit. The package came from a standalone repository and could move back out unchanged.

Source: #18, #12.
