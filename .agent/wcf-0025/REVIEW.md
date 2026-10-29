# Review

## Round 1 (reviewing 528c6ac)

Reviewed against `TASK.md` as written by commit 02f4fd8 (signed by the human, good signature). The history of `TASK.md` has two commits, both signed by the human: `5b6a1e3` (Add task) and `02f4fd8`. No "TASK.md changed by another role".

No earlier rounds, so no open findings to judge.

### Standards
No findings. `OPENING_PROMPT` is spelled once in `src/` (`src/foundry/agent_sandbox/sandbox.py:19`); the test's literal copy is deliberate, it pins the exact command. ARCHITECTURE.md step 4, `agent-kit/AGENTS.md:128-129`, planner `ROLE.md:14-15` and `GLOSSARY.md:79-80` agree with each other and with the code. No conflict with ADR 0004 (`sbxenv.yaml` untouched). No smells.

### Spec
No findings. Every acceptance criterion is met:
1. Command on every launch, with exact-command test: `sandbox.py:119-120`, `tests/agent_sandbox/test_sandbox.py` (passes).
2. One fixed sentence, no role named: `sandbox.py:19`.
3. Constant, never built from anything: `sandbox.py:119`.
4. ARCHITECTURE.md launch step 4: updated.
5. `agent-kit/AGENTS.md` "Taking turns": updated.
6. Planner `ROLE.md`: updated.
7. `ruff`, `mypy`, `tests/agent_sandbox` and `tests/test_docs.py` pass in a throwaway clone. The full host tier was not re-run by me.

Out of scope respected: `sbxenv.yaml` untouched, no per-role prompt.

### Behaviour
No findings. Both first launch and relaunch reach `attach()` (`launcher.py`), and `Host.exec` is `os.execvpe` with the argv as given, so no shell quoting applies. The prompt starts with no dash and follows `--`. Not reproduced against a real `sbx` (not installed here); the task says the human checked that `sbx env run` passes arguments after `--` to the agent.

Summary: Standards 0 findings, Spec 0, Behaviour 0; none block.

Verdict: approved
