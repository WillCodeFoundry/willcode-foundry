# Decisions

Each file records one decision: what was decided and why, and the options it replaced. A decision that changes gets a new record that supersedes the old one; accepted records aren't edited.

**Start here:** 0001, 0004, 0008 and 0010 are the core of how the foundry works.

| Theme | Decisions |
|---|---|
| Security model | [0001 GitHub enforces what must hold; hooks only guard](0001-github-enforces-hooks-only-guard.md) · [0008 The agent can't become root](0008-the-agent-cant-become-root.md) · [0005 Each sandbox gets only its own role's credentials](0005-credentials-per-role.md) |
| Sandboxes | [0004 A sandbox's definition and hardening are fixed](0004-sandboxes-are-immutable.md) · [0003 sbx is reached only through `agent_sandbox`](0003-sbx-behind-agent-sandbox.md) · [0010 Sandbox code runs from the read-only kit](0010-runtime-from-the-read-only-kit.md) |
| Projects and tasks | [0002 Every project matches one repo policy](0002-repo-policy-by-comparison.md) · [0006 A task is a branch plus its notes](0006-a-task-is-two-branches.md) · [0011 Task states follow a lifecycle written in code](0011-task-states.md) |
| Agents' skills | [0007 Skills are copied and edited in place](0007-skills-copied-not-installed.md) |
| Testing | [0009 Test against a modelled machine](0009-test-against-a-modelled-machine.md) |

To add one, take the next number and follow the format in `agent-kit/skills/domain-modeling/ADR-FORMAT.md`: a title, a few sentences of context, decision and why, and only the options worth remembering. Record a decision only when it is hard to reverse, surprising without context, and the result of a real trade-off.
