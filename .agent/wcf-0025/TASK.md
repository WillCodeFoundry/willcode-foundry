# Task wcf-0025: A launch starts the agent's turn without a typed message

## Goal
`foundry run` attaches you to Claude Code, which then waits until you type something. Every role already knows its job from `AGENTS.md`, its `ROLE.md` and the task notes, so that first message is always the same nudge. Each launch should send it, so a role starts working as soon as it is attached, and the turn-by-turn flow of ADR 0011 needs one command per turn, not a command and a message.

## Acceptance criteria
- [ ] Every launch, first launch and relaunch alike, runs `sbx env run --auto-approve <definition dir> -- "<opening prompt>"`. A test in `tests/agent_sandbox/test_sandbox.py` asserts the exact command `FakeHost.exec` receives.
- [ ] The opening prompt is one fixed sentence, spelled once in `src/foundry/agent_sandbox/`, that tells the agent to start its turn as `AGENTS.md` says. It names no role, so it suits every role, the planner included.
- [ ] The prompt is a constant, never built from the task, the role or any file the agent can write.
- [ ] `ARCHITECTURE.md`'s launch steps say that foundry sends the opening prompt when it attaches.
- [ ] `agent-kit/AGENTS.md` "Taking turns" says the agent's first message is foundry's opening prompt, and that the human may type the next.
- [ ] `agent-kit/roles/planner/ROLE.md` says to answer the opening prompt by asking the human what they want done, since it starts before the human has said anything.
- [ ] The host tier, `ruff` and `mypy` pass.

## Out of scope
- A prompt that differs by role or by turn: the role's instructions already differ.
- Starting a role without attaching you, such as a detached or unattended run.
- Changing the sandbox definition (`sbxenv.yaml`). Existing sandboxes must keep working without being recreated (ADR 0004).

## Context
- `src/foundry/agent_sandbox/sandbox.py`: `SbxCli.attach()` runs `sbx env run --auto-approve <definition dir>` through `Host.exec`. That call is the only change to the launch.
- `src/foundry/agent_sandbox/launcher.py`: `launch()` calls `attach()` after the sandbox is started.
- `tests/agent_sandbox/test_sandbox.py` and `tests/agent_sandbox/conftest.py`: `FakeHost`, whose `exec` records the command instead of running it.
- `agent-kit/AGENTS.md` "Taking turns" and `agent-kit/roles/planner/ROLE.md` "Method": where the instructions change.
- `sbx env run` passes everything after `--` to the agent as its arguments, as `sbx run` documents. The human checked it with the sbx installed here.

## Seams to test
- `SbxCli.attach()`, through `FakeHost` in `tests/agent_sandbox/conftest.py`: catches a missing or misplaced `--`, and a prompt built from anything but the constant.
- `tests/test_docs.py`, already run by the host tier: catches a broken link or path in the changed docs.

## Terms and decisions
- **Opening prompt** goes in `GLOSSARY.md`, under "Sandboxes and sessions": the fixed first message foundry sends when it attaches the agent.

## Open questions
