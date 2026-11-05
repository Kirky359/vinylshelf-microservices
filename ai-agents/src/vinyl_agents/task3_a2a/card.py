from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from vinyl_agents.tools.base import Tool


class AgentCardFactory:
    """Builds the Agent Card (served at /.well-known/agent-card.json) from the tools the agent exposes as skills."""

    def create(self, name: str, description: str, url: str, tools: list[Tool]) -> AgentCard:
        return AgentCard(
            name=name, description=description, url=url, version="1.0.0",
            capabilities=AgentCapabilities(streaming=False, push_notifications=False),
            default_input_modes=["text/plain", "application/json"],
            default_output_modes=["application/json", "text/plain"],
            skills=[AgentSkill(id=t.name, name=t.name.replace("_", " ").title(), description=t.description,
                               tags=list(t.tags), examples=list(t.examples)) for t in tools])
