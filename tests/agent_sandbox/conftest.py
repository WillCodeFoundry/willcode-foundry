import pytest

from foundry.agent_sandbox.host import Host
from tests.agent_sandbox.fakes import FakeHost


@pytest.fixture
def host() -> FakeHost:
    host = FakeHost()
    _: Host = host
    return host
