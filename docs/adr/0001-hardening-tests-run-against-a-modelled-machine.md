# Hardening's tests run against a modelled machine

`agent_runtime.harden` acts on a `Machine`: the sandbox's system files, sockets, the commands that reach root, and what the agent can write there. `SANDBOX` is the real one. Its tests run both modes, root then agent, against a temporary machine instead of testing each step and check on its own. That machine models the agent as a user who is neither the owner nor in the group of what it touches, judged by a path's "other" permission bits, rather than using the test user's real access: in a test, root and the agent are the same user, so real access would call every file root mode installs writable.

We chose this over keeping each step and check public and testing them one at a time. That is how review finding R12 on PR #20 got through: every part passed alone, and the sequence calling them, which nothing ran, crashed on every relaunch.

## Consequences

- What the model can't show stays a manual check: sbx's numeric docker group (the round trip shows the socket's gid is set, not that the agent is denied), a read-only mount's `EROFS`, and the real effect of chmod on sudo and of `passwd -l`. A real launch, and a second launch of the same sandbox, cover those.
- Listing a folder is real, not modelled, so the case for a kit folder that can't be listed runs only as a non-root user.
