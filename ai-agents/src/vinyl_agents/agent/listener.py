from abc import ABC

from vinyl_agents.exceptions import GuardrailViolation
from vinyl_agents.guardrails.token_budget import TokenBudget
from vinyl_agents.llm.schemas import TokenUsage


class AgentListener(ABC):
    """Observer of the agent loop (the console prints from here). All callbacks are optional."""

    def on_blocked(self, error: GuardrailViolation) -> None: ...
    def on_usage(self, usage: TokenUsage, budget: TokenBudget) -> None: ...
    def on_tool_call(self, round_no: int, name: str, args: dict) -> None: ...
    def on_tool_result(self, name: str, result: dict) -> None: ...
