from collections import deque

from vinyl_agents.llm.client import LlmClient
from vinyl_agents.llm.schemas import LlmResponse, Message, TokenUsage, ToolCall, ToolSpec


class ScriptedLlmClient(LlmClient):
    """Deterministic stand-in for the model: replays prepared answers. Used by the tests (no API key, no network)."""

    def __init__(self, script: list[LlmResponse]):
        self._script = deque(script)
        self.calls: list[dict] = []  # what the agent sent, for assertions

    async def generate(self, system_prompt: str, messages: list[Message], tools: list[ToolSpec],
                       max_output_tokens: int) -> LlmResponse:
        self.calls.append({"system_prompt": system_prompt, "messages": list(messages), "tools": [t.name for t in tools]})
        return self._script.popleft()

    @staticmethod
    def call(name: str, tokens: int = 100, **args) -> LlmResponse:
        return LlmResponse(tool_calls=[ToolCall(name=name, args=args)], model="scripted",
                           usage=TokenUsage(prompt_tokens=tokens - 10, completion_tokens=10, total_tokens=tokens))

    @staticmethod
    def say(text: str, tokens: int = 100) -> LlmResponse:
        return LlmResponse(text=text, model="scripted",
                           usage=TokenUsage(prompt_tokens=tokens - 10, completion_tokens=10, total_tokens=tokens))
