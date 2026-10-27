"""The code that runs inside an agent's sandbox, around the agent: hooks, session setup, hardening.

Built by foundry.runtime_build into the agent kit as ``.build/agent_runtime.pyz`` at every launch, and run
from the kit's read-only mount as ``/usr/bin/python3 -IS <pyz> <command>`` (see __main__). Standard library
only: it never imports ``foundry`` or ``yaml``, and tests/agent_kit/test_runtime.py checks that.

Kept free of anything an old interpreter can't parse: __main__ imports it before checking the version.

Errors: library code raises an exception whose only argument is the message, the full text the user will see;
__main__.run prints it and returns an exit code. A Claude Code hook
that enforces a rule blocks when it can't check that rule, and lets through what its rule doesn't cover.
"""
