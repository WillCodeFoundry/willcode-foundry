from pathlib import Path

from foundry.task import Task

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
TASK = Task("T1")
"""The task the kit's tests run as; its names come from Task, so its id is t1, as a sandbox would get."""
