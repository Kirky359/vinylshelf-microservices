import json
from typing import Any

from vinyl_agents.config import Settings
from vinyl_agents.guardrails.prompt_injection import PromptInjectionGuard

REDACTED = "[removed: suspicious content]"


class ToolOutputSanitizer:
    """Protection against INDIRECT prompt injection: a tool result (album title, ...) is data, never instructions.

    Strings that look like an attack are removed, the whole result is size-limited and marked as untrusted data.
    """

    def __init__(self, settings: Settings, injection_guard: PromptInjectionGuard):
        self._max_chars = settings.max_tool_output_chars
        self._guard = injection_guard

    def sanitize(self, tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
        cleaned = self._clean(result, tool_name)
        text = json.dumps(cleaned, ensure_ascii=False)
        if len(text) > self._max_chars:
            return {"untrusted_data": text[: self._max_chars], "truncated": True}
        return {"untrusted_data": cleaned}

    def _clean(self, value: Any, tool_name: str) -> Any:
        if isinstance(value, str):
            found = self._guard.scan(value)
            if found:
                self._guard.record_attempt(value, found, source=f"tool:{tool_name}")
                return REDACTED
            return value
        if isinstance(value, dict):
            return {k: self._clean(v, tool_name) for k, v in value.items()}
        if isinstance(value, list):
            return [self._clean(v, tool_name) for v in value]
        return value
