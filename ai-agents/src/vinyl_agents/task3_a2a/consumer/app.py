from vinyl_agents.agent.dependencies import AgentContainer
from vinyl_agents.guardrails.rate_limiter import SlidingWindowRateLimiter
from vinyl_agents.llm.prompts import PromptFactory
from vinyl_agents.task3_a2a.application import AgentApplication
from vinyl_agents.task3_a2a.card import AgentCardFactory
from vinyl_agents.task3_a2a.config import A2ASettings, get_a2a_settings
from vinyl_agents.task3_a2a.consumer.skills import consumer_skills
from vinyl_agents.task3_a2a.executor import SkillAgentExecutor
from vinyl_agents.task3_a2a.remote_client import RemoteAgentClient


class ConsumerAgentApplication(AgentApplication):
    """analytics-consumer as an A2A agent integrated with the Producer agent."""

    def __init__(self, container: AgentContainer | None = None, settings: A2ASettings | None = None,
                 producer: RemoteAgentClient | None = None):
        c = container or AgentContainer()
        self._settings = settings or get_a2a_settings()
        producer = producer or RemoteAgentClient(self._settings.producer_url)
        skills = consumer_skills(c.vinyl_service, producer, self._settings.delivery_wait_seconds)
        card = AgentCardFactory().create(
            "VinylShelf Consumer Agent",
            "Consumes VinylShelf events (transactional inbox), builds listening statistics and can ask the "
            "Producer agent over A2A to produce events.", self._settings.consumer_url, skills)
        text_agent = (c.agent(c.tool_registry(skills), system_prompt=PromptFactory.build("reasoning", PromptFactory.CONSUMER))
                      if c.llm_available else None)
        executor = SkillAgentExecutor(c.tool_registry(skills, sanitize=False), text_agent,
                                      SlidingWindowRateLimiter(self._settings.a2a_rate_limit_per_minute))
        super().__init__(card, executor)

    def start(self) -> None:
        self.run(self._settings.consumer_host, self._settings.consumer_port)
