# The agent can't become root: harden on the first launch, check as the agent on every launch

As root, the agent could rewrite the managed settings that decide which hooks run and what it may do. Its ways to root are sudo, `su` and Docker, whose daemon mounts the sandbox's own filesystem. On the first launch, while sudo still works, `harden` runs as root and closes all three. On every launch, `check-hardening` runs as the agent itself, with the groups sbx gives it, and the agent doesn't start unless all three are closed and it can't change its own rules. Other ways to root that an image might add, such as setuid binaries, aren't checked yet. `agent_runtime/hardening.py` describes how each way is closed.

## Considered options

- **Checking as root, or through `su agent`.** sbx gives the agent the docker group by number, so root, or a fresh login reading `/etc/group`, sees other permissions than the agent has.
- **Checking only on the first launch.** A sandbox re-attached later, or an image that adds a new way to root, would go unchecked.

Source: #18, #14.
