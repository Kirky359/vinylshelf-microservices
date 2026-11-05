from vinyl_agents.agent.dependencies import AgentContainer
from vinyl_agents.guardrails.rate_limiter import SlidingWindowRateLimiter
from vinyl_agents.llm.prompts import PromptFactory
from vinyl_agents.task3_a2a.application import AgentApplication
from vinyl_agents.task3_a2a.card import AgentCardFactory
from vinyl_agents.task3_a2a.config import A2ASettings, get_a2a_settings
from vinyl_agents.task3_a2a.executor import SkillAgentExecutor
from vinyl_agents.task3_a2a.producer.skills import producer_skills


class ProducerAgentApplication(AgentApplication):
    """collection-service (the producer of lab 3) as an A2A agent."""

    def __init__(self, container: AgentContainer | None = None, settings: A2ASettings | None = None):
        c = container or AgentContainer()
        self._settings = settings or get_a2a_settings()
        skills = producer_skills(c.vinyl_service)
        card = AgentCardFactory().create(
            "VinylShelf Producer Agent",
            "Produces VinylShelf collection events (album added, progress updated, album completed) through the "
            "transactional outbox and the completion SAGA.", self._settings.producer_url, skills)
        text_agent = (c.agent(c.tool_registry(skills), system_prompt=PromptFactory.build("reasoning", PromptFactory.PRODUCER))
                      if c.llm_available else None)
        executor = SkillAgentExecutor(c.tool_registry(skills, sanitize=False), text_agent,
                                      SlidingWindowRateLimiter(self._settings.a2a_rate_limit_per_minute))
        super().__init__(card, executor)

    def start(self) -> None:
        self.run(self._settings.producer_host, self._settings.producer_port)
