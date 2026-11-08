"""`session-setup`: the agent user's part of session-init, run alone, by hand or in tests."""

from agent_runtime import contract, session_setup
from agent_runtime.commands import progress_on_stdout


def main() -> None:
    """Composition root: set the sandbox up from this process's session variables, showing its progress."""
    variables = contract.read_session_variables()
    with progress_on_stdout():
        session_setup.set_up(variables)
