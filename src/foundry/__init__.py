"""willcode-foundry: run coding agents in sandboxes, one role per task.

Errors: library code raises an exception whose only argument is the message, the full text the user will see
(FoundryError, SandboxError, agent_runtime's GitError); foundry.cli.main, the one entry point, prints it and
returns 1.
"""
