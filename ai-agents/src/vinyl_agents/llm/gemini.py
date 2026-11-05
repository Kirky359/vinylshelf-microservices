import asyncio
from typing import Any

from google import genai
from google.genai import errors, types

from vinyl_agents.config import Settings
from vinyl_agents.exceptions import LlmError
from vinyl_agents.llm.client import LlmClient
from vinyl_agents.llm.schemas import LlmResponse, Message, TokenUsage, ToolCall, ToolSpec


class GeminiClient(LlmClient):
    """Google Gemini through the google-genai SDK. Automatic function calling is OFF: the agent loop executes the
    tools itself, so every call passes through our guardrails."""

    MAX_ATTEMPTS = 5
    RETRY_CODES = (429, 500, 503, 504)

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise LlmError("GEMINI_API_KEY is not set (see .env.example)")
        self._client = genai.Client(api_key=settings.gemini_api_key,
                                    http_options=types.HttpOptions(timeout=int(settings.gemini_timeout_seconds * 1000)))
        self._model = settings.gemini_model
        self._thinking_budget = settings.gemini_thinking_budget

    async def generate(self, system_prompt: str, messages: list[Message], tools: list[ToolSpec],
                       max_output_tokens: int) -> LlmResponse:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_output_tokens,
            temperature=0.2,
            tools=[types.Tool(function_declarations=[self._declaration(t) for t in tools])] if tools else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=(types.ThinkingConfig(thinking_budget=self._thinking_budget)
                             if self._thinking_budget is not None else None),
        )
        contents = [self._to_content(m) for m in messages]
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                response = await self._client.aio.models.generate_content(model=self._model, contents=contents,
                                                                          config=config)
                return self._to_response(response)
            except errors.APIError as exc:
                if exc.code in self.RETRY_CODES and attempt < self.MAX_ATTEMPTS:
                    await asyncio.sleep(2 * attempt)  # the model is overloaded or rate limited: wait and retry
                    continue
                raise LlmError(f"Gemini request failed: {exc}") from exc
            except Exception as exc:  # network errors, timeouts
                raise LlmError(f"Gemini request failed: {exc}") from exc

    @staticmethod
    def _declaration(tool: ToolSpec) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(name=tool.name, description=tool.description,
                                         parameters_json_schema=tool.parameters)

    @staticmethod
    def _to_content(message: Message) -> types.Content:
        if message.provider_payload is not None:
            return message.provider_payload  # the model's own turn, sent back unchanged (keeps thought signatures)
        if message.role == "tool":
            return types.Content(role="user", parts=[
                types.Part.from_function_response(name=r.name, response=r.result) for r in message.tool_results])
        return types.Content(role=message.role, parts=[types.Part.from_text(text=message.text)])

    def _to_response(self, response: Any) -> LlmResponse:
        usage = response.usage_metadata
        token_usage = TokenUsage(prompt_tokens=usage.prompt_token_count or 0,
                                 completion_tokens=(usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
                                 total_tokens=usage.total_token_count or 0) if usage else TokenUsage()
        candidate = response.candidates[0] if response.candidates else None
        content = candidate.content if candidate else None
        parts = (content.parts or []) if content else []
        calls = [ToolCall(name=p.function_call.name, args=dict(p.function_call.args or {}))
                 for p in parts if p.function_call]
        text = "".join(p.text for p in parts if p.text and not p.thought)
        return LlmResponse(text=text, tool_calls=calls, usage=token_usage, model=self._model, provider_payload=content)
