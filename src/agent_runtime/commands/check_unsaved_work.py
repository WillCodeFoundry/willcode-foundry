"""`check-unsaved-work`: the checkout status, which foundry runs in the sandbox after each agent run and prints."""

from agent_runtime import contract
from agent_runtime.unsaved_work import describe_unsaved_work


def main() -> int:
    """Composition root: check both checkouts the session variables name, and report them."""
    return report(describe_unsaved_work(contract.read_session_variables()))


def report(unsaved: list[str]) -> int:
    """Print each checkout's unsaved work, or that both are saved, and return the exit code: 1 unless both are."""
    if unsaved:
        print("\n".join(unsaved))
        return 1
    print("both checkouts are saved on origin")
    return 0
