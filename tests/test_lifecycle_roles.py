"""Every role a lifecycle assigns a state to is one this foundry has: listed in config/foundry.yaml, with its dir
in the agent kit. Otherwise `foundry task run` would refuse the task on that turn."""

import pytest

from agent_runtime.agent_kit import AgentKit
from agent_runtime.task.lifecycles import LIFECYCLES
from foundry import config
from tests.support import AGENT_KIT_SOURCE, REPOSITORY

ROLES = sorted(
    {
        (lifecycle.name, state.role)
        for lifecycle in LIFECYCLES.values()
        for state in lifecycle.states.values()
        if state.role is not None
    }
)


@pytest.mark.parametrize(("lifecycle", "role"), ROLES)
def test_each_states_role_is_a_configured_role_with_its_dir_in_the_kit(lifecycle: str, role: str) -> None:
    assert role in config.load(REPOSITORY).roles
    assert AgentKit(AGENT_KIT_SOURCE).role(role).missing() == []
