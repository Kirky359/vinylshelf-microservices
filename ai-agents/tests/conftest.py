import pytest

from tests.fake_backend import FakeVinylShelf
from vinyl_agents.agent.dependencies import AgentContainer
from vinyl_agents.config import Settings
from vinyl_agents.task2_mcp_server.config import McpSettings
from vinyl_agents.task3_a2a.config import A2ASettings
from vinyl_agents.vinylshelf.client import VinylShelfClient


@pytest.fixture
def backend() -> FakeVinylShelf:
    return FakeVinylShelf()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, token_log_path=tmp_path / "tokens.json", injection_log_path=tmp_path / "inj.json",
                    saga_wait_seconds=2)


@pytest.fixture
def a2a_settings() -> A2ASettings:
    return A2ASettings(_env_file=None, delivery_wait_seconds=2, producer_url="http://producer.test",
                       consumer_url="http://consumer.test")


@pytest.fixture
def mcp_settings() -> McpSettings:
    return McpSettings(_env_file=None, mcp_rate_limit_per_minute=100)


def make_container(settings: Settings, backend: FakeVinylShelf, llm=None) -> AgentContainer:
    return AgentContainer(settings, VinylShelfClient(settings, backend.transport()), llm)


@pytest.fixture
def container(settings, backend) -> AgentContainer:
    return make_container(settings, backend)
