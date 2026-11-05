from abc import ABC, abstractmethod

from vinyl_agents.llm.schemas import LlmResponse, Message, ToolSpec


class LlmClient(ABC):
    """Port to a language model with function calling. Implementations: GeminiClient, ScriptedLlmClient (tests)."""

    @abstractmethod
    async def generate(self, system_prompt: str, messages: list[Message], tools: list[ToolSpec],
                       max_output_tokens: int) -> LlmResponse:
        """One model turn: either plain text or a list of tool calls."""
